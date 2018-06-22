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

import base64
import hashlib
import hmac
import json
import logging
import time
from pprint import pformat
from typing import List, Optional

import dateutil.parser
import requests

from pyexchange.util import sort_trades
from pymaker import Wad
from pymaker.util import http_response_summary


class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_remaining: Optional[Wad]):

        assert(isinstance(order_id, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_remaining, Wad) or (amount_remaining is None))

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
                 trade_id: id,
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int))
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


class GOPAXApi:
    """GOPAX API interface.

    Developed according to the following manual:
    <https://www.gopax.co.kr/API?locale=en>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, api_secret: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(api_secret, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

    def get_balances(self):
        return self._http_get("/balances", "")

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        result = self._http_get("/orders", "")

        orders = list(map(lambda item: Order(order_id=int(item['id']),
                                             pair=str(item['tradingPairName']),
                                             is_sell=item['side'] == 'sell',
                                             price=Wad.from_number(item['price']),
                                             amount=Wad.from_number(item['amount']),
                                             amount_remaining=None), result))

        orders = list(filter(lambda order: order.pair == pair, orders))

        return orders

    def get_order(self, order_id: int) -> Order:
        assert(isinstance(order_id, int))

        item = self._http_get(f"/orders/{order_id}", "")

        order = Order(order_id=int(item['id']),
                      pair=str(item['tradingPairName']),
                      is_sell=item['side'] == 'sell',
                      price=Wad.from_number(item['price']),
                      amount=Wad.from_number(item['amount']),
                      amount_remaining=Wad.from_number(item['remaining']))

        return order

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> int:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        params = {
            "type": "limit",
            "side": "sell" if is_sell else "buy",
            "price": str(price),
            "amount": str(amount),
            "tradingPairName": pair
        }
        result = self._http_post("/orders", params)
        order_id = int(result['id'])

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: int) -> bool:
        assert(isinstance(order_id, int))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_delete(f"/orders/{order_id}")
        success = result == {}

        if success:
            self.logger.info(f"Cancelled order #{order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}")

        return success

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_get("/trades", f"trading-pair-name={pair}")

        trades = list(map(lambda item: Trade(trade_id=int(item['id']),
                                             timestamp=int(dateutil.parser.parse(item['timestamp']).timestamp()),
                                             pair=str(item['tradingPairName']),
                                             is_sell=item['side'] == 'sell',
                                             price=Wad.from_number(item['price']),
                                             amount=Wad.from_number(item['baseAmount'])), result))

        return sort_trades(trades)

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_unauthenticated_get(f"/trading-pairs/{pair}/trades", "")

        return list(map(lambda item: Trade(trade_id=int(item['id']),
                                           timestamp=int(dateutil.parser.parse(item['time']).timestamp()),
                                           pair=pair,
                                           is_sell=item['side'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount'])), result))

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"GOPAX API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"GOPAX API invalid JSON response: {http_response_summary(result)}")

        if 'errormsg' in data:
            raise Exception(f"GOPAX API negative response: {http_response_summary(result)}")

        return data

    def _prepare_headers(self, method: str, request_path: str, request_body: str):
        assert(isinstance(method, str))
        assert(isinstance(request_path, str))
        assert(isinstance(request_body, str))

        nonce = str(time.time())
        headers = {
            "API-KEY": self.api_key,
            "SIGNATURE": self._create_signature(nonce, method, request_path, request_body),
            "NONCE": nonce
        }

        return headers

    def _create_signature(self, nonce: str, method: str, request_path: str, request_body: str):
        assert(isinstance(nonce, str))
        assert(isinstance(method, str))
        assert(isinstance(request_path, str))
        assert(isinstance(request_body, str))

        what = nonce + method + request_path + request_body
        what = bytes(what, "utf-8")

        key = base64.b64decode(self.api_secret)
        signature = hmac.new(key, what, hashlib.sha512)

        return base64.b64encode(signature.digest())

    def _http_unauthenticated_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         timeout=self.timeout))

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         headers=self._prepare_headers('GET', resource, ''),
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        data = json.dumps(params)

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                          data=data,
                                          headers={
                                              **self._prepare_headers('POST', resource, data),
                                              **{"Content-Type": "application/json"}
                                          },
                                          timeout=self.timeout))

    def _http_delete(self, resource: str):
        assert(isinstance(resource, str))

        return self._result(requests.delete(url=f"{self.api_server}{resource}",
                                            headers=self._prepare_headers('DELETE', resource, ''),
                                            timeout=self.timeout))
