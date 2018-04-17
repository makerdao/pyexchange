# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus, bargst
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import logging
import threading
import time
from pprint import pformat
from typing import Optional, List

import dateutil.parser
import pytz
import requests

import pymaker.zrx
from pyexchange.util import sort_trades
from pymaker import Wad
from pymaker.sign import eth_sign
from pymaker.util import hexstring_to_bytes, http_response_summary
from web3 import Web3


class Order:
    def __init__(self,
                 order_id: str,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_remaining: Wad):

        assert(isinstance(order_id, str))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_remaining, Wad))

        self.order_id = order_id
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.amount_remaining = amount_remaining

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount_remaining*self.price if self.is_sell else self.amount_remaining

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount_remaining if self.is_sell else self.amount_remaining*self.price

    def __repr__(self):
        return pformat(vars(self))


class DdexApi:
    """Ddex API interface.

    Developed according to the following manual:
    <https://docs.ddex.io/>.
    """

    logger = logging.getLogger()

    def __init__(self, web3: Web3, api_server: str, timeout: float):
        assert(isinstance(web3, Web3) or (web3 is None))
        assert(isinstance(api_server, str))
        assert(isinstance(timeout, float))

        self.web3 = web3
        self.api_server = api_server
        self.timeout = timeout

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get(f"/v2/markets/{pair}/ticker", f"")

    def get_markets(self):
        return self._http_get("/v2/markets", f"")

    def get_balances(self):
        return self._http_get_signed("/v2/account/lockedBalances", "")

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders = self._http_get_signed("/v2/orders", f"market_id={pair}")

        return list(map(lambda item: Order(order_id=item['id'],
                                           pair=pair,
                                           is_sell=item['side'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_remaining=Wad.from_number(item['availableAmount'])),
                        list(orders['data']['orders'])))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> int:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        # build order
        order = {
            "amount": str(amount),
            "price": str(price),
            "side": 'sell' if is_sell else 'buy',
            "market_id": pair,
        }
        result = self._http_post_signed("/v2/orders/build", order)
        order_id = result['data']['orderId']
        unsignedOrder = result['data']['unsignedOrder']
        fee = result['data']['feeAmount']

        # sign order
        signature = eth_sign(hexstring_to_bytes(order_id), self.web3)
        result = self._http_post_signed("/v2/orders", {"orderId": order_id, "signature": signature})

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}, fee {float(fee)*100:.4f}%) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_delete_signed(f"/v2/orders/{order_id}", "")
        print(result)
        success = result['status']

        if success == 0:
            self.logger.info(f"Cancelled order #{order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}")

        return success

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Ddex API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Ddex API invalid JSON response: {http_response_summary(result)}")

        if 'status' in data and data['status'] is not 0:
            raise Exception(f"Ddex API negative response: {http_response_summary(result)}")

        return data

    def _create_signature(self, msg: str) -> str:
        assert(isinstance(msg, str))

        try:
            from sha3 import keccak_256
        except ImportError:
            from sha3 import sha3_256 as keccak_256

        message = bytes(msg, 'utf-8')
        return eth_sign(message, self.web3)

    def _create_sig_header(self, staticMessage: str):
        assert(isinstance(staticMessage, str))

        # Ddex-Authentication: tradingAddress#*staticMessage#*signature
        tradingAddress = self.web3.eth.defaultAccount.lower()
        signature = self._create_signature(staticMessage)
        return f"{tradingAddress}#*{staticMessage}#*{signature}"

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         timeout=self.timeout))

    def _http_get_signed(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        auth_token = self._create_sig_header('DDEX-SIGN-IN')
        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         headers={
                                            "Ddex-Authentication": auth_token,
                                         },
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                          json=params,
                                          headers={
                                              "API-KEY": self.api_key
                                          },
                                          timeout=self.timeout))

    def _http_post_signed(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        auth_token = self._create_sig_header('DDEX-SIGN-IN')
        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                         json=params,
                                         headers={
                                            "Ddex-Authentication": auth_token,
                                         },
                                         timeout=self.timeout))

    def _http_delete_signed(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        auth_token = self._create_sig_header('DDEX-SIGN-IN')
        return self._result(requests.delete(url=f"{self.api_server}{resource}?{params}",
                                         headers={
                                            "Ddex-Authentication": auth_token,
                                         },
                                         timeout=self.timeout))
