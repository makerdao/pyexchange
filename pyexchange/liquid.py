# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 grandizzy
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
import requests
import threading
import json
import time
import jwt

from typing import Optional, List
from pprint import pformat

from pymaker import Wad
from pymaker.util import http_response_summary
from pyexchange.api import PyexAPI


class Order:
    def __init__(self,
                 order_id: str,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 filled_amount: Wad):

        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(filled_amount, Wad))

        self.order_id = order_id
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.filled_amount = filled_amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        remaining_amount = self.amount - self.filled_amount
        return remaining_amount*self.price if self.is_sell else remaining_amount

    @property
    def remaining_sell_amount(self) -> Wad:
        remaining_amount = self.amount - self.filled_amount
        return remaining_amount if self.is_sell else remaining_amount*self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def to_order(item):
        return Order(order_id=item['id'],
                     pair=item['currency_pair_code'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['quantity']),
                     filled_amount=Wad.from_number(item['filled_quantity']))


class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def to_trade(pair, trade):
        return Trade(trade_id=str(trade['id']),
                     timestamp=int(trade['created_at']),
                     pair=pair,
                     is_sell=trade['taker_side'] == 'buy',
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['quantity']))


class LiquidApi(PyexAPI):
    """Liquid API interface.

    https://developers.liquid.com
    """
    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self.last_nonce = 0
        self.last_nonce_lock = threading.Lock()

    def get_markets(self):
        return self._http_request("GET", "/products", {})

    def get_pair(self, pair: str):
        assert(isinstance(pair, str))
        return next(filter(lambda symbol: symbol['currency_pair_code'] == pair, self.get_markets()))

    def _get_product_id(self, pair: str):
        assert(isinstance(pair, str))
        return next(filter(lambda symbol: symbol['currency_pair_code'] == pair, self.get_markets()))['id']

    def get_balances(self):
        return self._http_authenticated("GET", "/accounts/balance", {})

    def get_orders(self, pair: str):
        assert(isinstance(pair, str))

        product_id = self._get_product_id(pair)

        result = self._http_authenticated("GET", f"/orders?product_id={product_id}&status=live", {})

        if result['models'] is None:
            return []

        return list(map(lambda item: Order.to_order(item), result['models']))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad):
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        product_id = self._get_product_id(pair)

        data = {
            "order_type": "limit",
            "product_id": product_id,
            "side": "sell" if is_sell else "buy",
            "quantity": str(amount),
            "price": str(price)
        }

        self.logger.info(f"Placing order ({data['order_type']}, amount {data['quantity']} of {pair},"
                         f" price {data['price']})...")

        result = self._http_authenticated("POST", "/orders", data)
        order_id = str(result['id'])

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str):
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated("PUT", f"/orders/{order_id}/cancel", {})

        if order_id == str(result['id']):
            self.logger.info(f"Cancelled order #{order_id}")
            return True

        self.logger.info(f"Failed to cancel order #{order_id}")
        return False

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        product_id = self._get_product_id(pair)

        result = self._http_authenticated("GET", f"/executions/me?product_id={product_id}", {})

        return list(map(lambda item: Trade.to_trade(pair, item), result['models']))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        product_id = self._get_product_id(pair)

        result = self._http_request("GET", f"/executions?product_id={product_id}&limit=100&page={page_number}", {})

        return list(map(lambda item: Trade.to_trade(pair, item), result['models']))

    def _choose_nonce(self) -> int:
        with self.last_nonce_lock:
            timed_nonce = int(time.time()*1000)

            if self.last_nonce + 1 > timed_nonce:
                self.logger.info(f"Wanted to use nonce '{timed_nonce}', but last nonce is '{self.last_nonce}'")
                self.logger.info(f"In this case using '{self.last_nonce + 1}' instead")

                self.last_nonce += 1
            else:
                self.last_nonce = timed_nonce

            return self.last_nonce

    def _http_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    def _http_authenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        max_attempts = 3
        for attempt in range(0, max_attempts):
            our_nonce = self._choose_nonce()

            auth_payload = {
                "path": resource,
                "nonce": our_nonce,
                "token_id": self.api_key
            }

            signature = jwt.encode(auth_payload, self.secret_key, 'HS256')

            data = json.dumps(body, separators=(',', ':'))

            result = self._result(requests.request(method=method,
                                                 url=f"{self.api_server}{resource}",
                                                 data=data,
                                                 headers={
                                                     "X-Quoine-API-Version": "2",
                                                     "Content-Type":"application/json",
                                                     "X-Quoine-Auth":signature
                                                 },
                                                 timeout=self.timeout))

            # result will be `None` if we need to readjust nonce
            # in this case we will try again in the next iteration

            if result is not None:
                return result

    def _result(self, result, our_nonce: Optional[int] = None) -> Optional[dict]:

        if result.status_code == 401 and f"Your nonce {our_nonce} is smaller than or equal last nonce" in result.json()["message"]:
            return None

        if not result.ok:
            raise Exception(f"Liquid API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Liquid API invalid JSON response: {http_response_summary(result)}")

        return data
