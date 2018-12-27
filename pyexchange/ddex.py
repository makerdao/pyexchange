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

import logging
import time
from pprint import pformat
from typing import Optional, List

import requests

from pyexchange.util import sort_trades
from pymaker import Wad, Address
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


class Trade:
    def __init__(self,
                 trade_id: Optional[str],
                 timestamp: int,
                 pair: str,
                 is_sell: Optional[bool],
                 price: Wad,
                 amount: Wad,
                 createdAt: int):
        assert(isinstance(trade_id, str) or (trade_id is None))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool) or (is_sell is None))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(createdAt, int))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.createdAt = createdAt

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount and \
               self.createdAt == other.createdAt

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount,
                     self.createdAt))

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
        self.version = "v3"

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get(f"/{self.version}/markets/{pair}/ticker", {})

    def get_markets(self):
        return self._http_get(f"/{self.version}/markets", {})

    def get_balances(self):
        return self._http_get_signed(f"/{self.version}/account/lockedBalances", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders = self._http_get_signed(f"/{self.version}/orders?marketId={pair}", {})

        return list(map(lambda item: Order(order_id=item['id'],
                                           pair=pair,
                                           is_sell=item['side'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_remaining=Wad.from_number(item['availableAmount'])),
                        list(orders['data']['orders'])))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        # build order
        order = self._build_order(amount, price, is_sell, pair)

        result = self._http_post_signed(f"/{self.version}/orders/build", order)
        order_id = result['data']['order']['id']
        unsignedOrder = result['data']['order']['json']
        fee = self._get_fee_rate(result)

        # sign order
        signature = eth_sign(hexstring_to_bytes(order_id), self.web3)
        result = self._http_post_signed(f"/{self.version}/orders", {"orderId": order_id, "signature": signature})

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}, fee {float(fee)*100:.4f}%) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_delete_signed(f"/{self.version}/orders/{order_id}", {})
        success = result['status']

        if success == 0:
            self.logger.info(f"Cancelled order #{order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}")

        return success == 0

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        per_page = 100
        page_filter = f"page={page_number}&per_page={per_page}"
        result = self._http_get_signed(f"/{self.version}/markets/{pair}/trades/mine?{page_filter}", {})['data']
        totalPages = result['totalPages']
        currentPage = result['currentPage']
        self.logger.debug(f'totalPages={totalPages};currentPage={currentPage}')

        # Oldest trades are on first page

        trades  = result['trades']
        trades = list(filter(lambda item: item['status'] == 'successful', trades))

        trades = list(map(lambda item: Trade(trade_id=item['transactionId'],
                                             timestamp=int(item['executedAt']/1000),
                                             pair=pair,
                                             is_sell= Address(item['buyer']) != Address(self.web3.eth.defaultAccount),
                                             price=Wad.from_number(item['price']),
                                             amount=Wad.from_number(item['amount']),
                                             createdAt=int(item['createdAt']/1000)), trades))

        return sort_trades(trades)

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        per_page = 100
        page_filter = f"page={page_number}&per_page={per_page}"
        result = self._http_get(f"/{self.version}/markets/{pair}/trades?{page_filter}", {})['data']
        totalPages = result['totalPages']
        currentPage = result['currentPage']
        self.logger.debug(f'totalPages={totalPages};currentPage={currentPage}')

        # Oldest trades are on first page

        trades  = result['trades']
        trades = list(filter(lambda item: item['status'] == 'successful', trades))

        return list(map(lambda item: Trade(trade_id=None,
                                           timestamp=int(item['executedAt']/1000),
                                           pair=pair,
                                           is_sell=None,
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           createdAt=int(item['createdAt']/1000)), trades))

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

        return eth_sign(bytes(msg, 'utf-8'), self.web3)

    def _create_sig_header(self):

        message = "HYDRO-AUTHENTICATION@" + str(int(time.time() * 1000))

        # https://docs.ddex.io/#authentication
        tradingAddress = self.web3.eth.defaultAccount.lower()
        signature = self._create_signature(message)
        return f"{tradingAddress}#{message}#{signature}"

    def _http_get(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.get(url=f"{self.api_server}{resource}",
                                         json=params,
                                         timeout=self.timeout))

    def _http_get_signed(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.get(url=f"{self.api_server}{resource}",
                                         json=params,
                                         headers={
                                            "Hydro-Authentication": self._create_sig_header(),
                                         },
                                         timeout=self.timeout))

    def _http_post_signed(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                         json=params,
                                         headers={
                                            "Hydro-Authentication": self._create_sig_header(),
                                         },
                                         timeout=self.timeout))

    def _http_delete_signed(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.delete(url=f"{self.api_server}{resource}",
                                         json=params,
                                         headers={
                                            "Hydro-Authentication": self._create_sig_header(),
                                         },
                                         timeout=self.timeout))

    def _get_fee_rate(self, result):
        return result['data']['order']['makerFeeRate']

    def _build_order(self, amount, price, is_sell, pair):
        return {
            "amount": str(amount),
            "price": str(price),
            "side": 'sell' if is_sell else 'buy',
            "orderType": "limit",
            "marketId": pair,
        }


class DdexApiV2(DdexApi):

    def __init__(self, web3: Web3, api_server: str, timeout: float):
        assert(isinstance(web3, Web3) or (web3 is None))
        assert(isinstance(api_server, str))
        assert(isinstance(timeout, float))

        self.web3 = web3
        self.api_server = api_server
        self.timeout = timeout
        self.version = "v2"

    def _get_fee_rate(self, result):
        return result['data']['order']['feeAmount']

    def _build_order(self, amount, price, is_sell, pair):
        return {
            "amount": str(amount),
            "price": str(price),
            "side": 'sell' if is_sell else 'buy',
            "marketId": pair,
        }
