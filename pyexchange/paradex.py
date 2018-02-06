# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus
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
import time
from pprint import pformat
from typing import Optional, List

import pytz
import requests
from web3 import Web3

import pymaker.zrx
from pymaker import Wad
from pymaker.sign import eth_sign_with_keyfile
from pymaker.zrx import ZrxExchange


class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_remaining: Wad):

        assert(isinstance(order_id, int))
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
    def remaining_sell_amount(self) -> Wad:
        return self.amount_remaining if self.is_sell else self.amount_remaining*self.price

    def __repr__(self):
        return pformat(vars(self))


class ParadexApi:
    """Paradex API interface.

    Developed according to the following manual:
    <https://github.com/ParadexRelayer/Consumer-API-docs>.
    """

    logger = logging.getLogger()

    def __init__(self, web3: Web3, zrx_exchange: ZrxExchange, api_server: str, api_key: str, key_file: str, key_password: str, timeout: float):
        assert(isinstance(web3, Web3))
        assert(isinstance(zrx_exchange, ZrxExchange))
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(key_file, str))
        assert(isinstance(key_password, str))
        assert(isinstance(timeout, float))

        self.web3 = web3
        self.zrx_exchange = zrx_exchange
        self.api_server = api_server
        self.api_key = api_key
        self.key_file = key_file
        self.key_password = key_password
        self.timeout = timeout
        self.nonce = 0

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get("/v0/ticker", f"market={pair}")

    def get_balances(self):
        return self._http_post("/v0/balances", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders_open = self._http_post("/v0/orders", {
            'market': pair,
            'state': 'open'
        })

        orders_unfunded = self._http_post("/v0/orders", {
            'market': pair,
            'state': 'unfunded'
        })

        return list(map(lambda item: Order(order_id=int(item['id']),
                                           pair=pair,
                                           is_sell=item['type'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_remaining=Wad.from_number(item['amountRemaining'])),
                        list(orders_open) + list(orders_unfunded)))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad, expiry: int) -> int:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(expiry, int))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        order_params = self._http_post("/v0/orderParams", {
            'market': pair,
            'orderType': 'sell' if is_sell else 'buy',
            'price': str(price),
            'amount': str(amount),
            'expirationDate': datetime.datetime.fromtimestamp(time.time() + expiry, pytz.UTC).strftime("%Y-%m-%d %H:%M:%S.000000%z")
        })

        order = pymaker.zrx.Order.from_json(self.zrx_exchange, order_params['zrxOrder'])
        order = self.zrx_exchange.sign_order(order)

        result = self._http_post("/v0/order", {
            'exchangeContractAddress': str(order.exchange_contract_address.address),
            'expirationUnixTimestampSec': str(order.expiration),
            'feeRecipient': str(order.fee_recipient.address),
            'maker': str(order.maker.address),
            'makerFee': str(order.maker_fee.value),
            'makerTokenAddress': str(order.pay_token.address),
            'makerTokenAmount': str(order.pay_amount.value),
            'salt': str(order.salt),
            'taker': str(order.taker.address),
            'takerFee': str(order.taker_fee.value),
            'takerTokenAddress': str(order.buy_token.address),
            'takerTokenAmount': str(order.buy_amount.value),
            'v': str(order.ec_signature_v),
            'r': str(order.ec_signature_r),
            's': str(order.ec_signature_s),
            'feeId': order_params['fee']['id']
        })
        order_id = result['id']

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}) as #{order_id}")

        return order_id

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Paradex API invalid HTTP response: {result.status_code} {result.reason}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Paradex API invalid JSON response: {result.text}")

        if 'error' in data:
            if 'code' in data['error'] and data['error']['code'] == 107:
                new_nonce = data['error']['currentNonce'] + 1
                self.logger.info(f"Invalid nonce, tried {self.nonce - 1} but instructed to change to {new_nonce}")
                self.nonce = new_nonce

                return None

            raise Exception(f"Negative Paradex response: {data}")

        return data

    def _create_signature(self, params: dict) -> str:
        assert(isinstance(params, dict))

        try:
            from sha3 import keccak_256
        except ImportError:
            from sha3 import sha3_256 as keccak_256

        keys = ''
        values = ''
        for key in sorted(params.keys()):
            keys += key
            values += str(params[key])

        raw_message = keccak_256(bytes(keys + values, 'utf-8')).digest()
        return eth_sign_with_keyfile(raw_message, True, self.key_file, self.key_password)

    def _create_vrs_header(self, params: dict):
        assert(isinstance(params, dict))

        signature = self._create_signature(params)
        if signature.endswith("1c"):
            return (signature[0:130] + "01")[2:]
        elif signature.endswith("1b"):
            return (signature[0:130] + "00")[2:]
        else:
            raise Exception(f"Invalid signature: {signature}")

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         headers={"API-KEY": self.api_key},
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        max_attempts = 3
        for attempt in range(0, max_attempts):
            params_with_nonce = params.copy()
            params_with_nonce['nonce'] = self.nonce
            self.nonce += 1

            result = self._result(requests.post(url=f"{self.api_server}{resource}",
                                                json=params_with_nonce,
                                                headers={
                                                    "API-KEY": self.api_key,
                                                    "API-VRS": self._create_vrs_header(params_with_nonce)
                                                },
                                                timeout=self.timeout))

            # result will be `None` if we need to readjust nonce
            # in this case we will try again in the next iteration
            if result is not None:
                return result

        raise Exception(f"Couldn't get a response despite {max_attempts} attempts to readjust the nonce")
