# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2019 reverendus, grandizzy
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
from pprint import pformat
from typing import Optional, List

import dateutil.parser
import requests
import time
import hmac
import hashlib

import uuid
import base64

from urllib.parse import urlencode

from pyexchange.api import PyexAPI

from pymaker.numeric import Wad
from pymaker.util import http_response_summary

# API Documentation: https://etorox.github.io/docs/#/

class Order:
    def __init__(self,
                 order_id: str,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 remaining_amount: Wad):

        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(remaining_amount, Wad))

        self.order_id = order_id
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.remaining_amount = remaining_amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.remaining_amount*self.price if self.is_sell else self.remaining_amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.remaining_amount if self.is_sell else self.remaining_amount*self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def to_order(item):
        return Order(order_id=item['OrderUuid'],
                     pair=item['Exchange'],
                     is_sell=True if item['OrderType'] == 'LIMIT_SELL' else False,
                     price=Wad.from_number(item['Limit']),
                     amount=Wad.from_number(item['Quantity']),
                     remaining_amount=Wad.from_number(item['QuantityRemaining']))


class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 pair: Optional[str],
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str) or (pair is None))
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


class EToroApi(PyexAPI):
    """eToro API interface.

    Developed according to the following manual:
    <https://etorox.github.io/dxocs/#/>.
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

    def get_markets(self):
        return self._http_authenticated_request("GET", "/api/v1/instruments", {})['result']

    def get_pair(self, pair: str):
        assert(isinstance(pair, str))
        return next(filter(lambda symbol: symbol['MarketName'] == pair, self.get_markets()))

    def get_balances(self):
        return self._http_authenticated_request("GET", "/api/v1/balances", {})['result']

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        params = {
            "instrument_id": pair,
            "state": "",
            "limit": "",
            "before": ""
        }

        orders = self._http_authenticated_request("GET", "/api/v1/orders", params)['result']

        return list(map(lambda item: Order.to_order(item), orders))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        params = {
            "quantity": str(amount),
            "rate": str(price),
            "market": pair
        }

        order_type = "selllimit" if is_sell else "buylimit"

        self.logger.info(f"Placing order ({order_type}, amount {params['quantity']} of {pair},"
                         f" price {params['rate']})...")

        response = self._http_authenticated_request("POST", f"/api/v1/orders", params)

        if response['success'] is False:
            raise Exception(f"Bittrex Failed to place order {response['message']}")

        order_id = response['result']['uuid']

        self.logger.info(f"Placed order type {order_type}, id #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        params = {
            "uuid": order_id
        }

        result = self._http_authenticated_request("GET", "/api/v1/orders/{order_id}", params)

        return result['success']

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        params = {
            'market': pair
        }

        result = self._http_authenticated_request("GET", "/api/v1/trades", params)['result']

        return list(map(lambda item: Trade(trade_id=item['OrderUuid'],
                                           timestamp=int(dateutil.parser.parse(item['TimeStamp'] + 'Z').timestamp()),
                                           pair=item['Exchange'],
                                           is_sell=item['OrderType'] == 'LIMIT_SELL',
                                           price=Wad.from_number(item['PricePerUnit']),
                                           amount=Wad.from_number(item['Quantity'] - item['QuantityRemaining'])), result))

    def _http_request(self, method: str, resource: str, params: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        url=f"{self.api_server}{resource}"
        if params:
            url=f"{self.api_server}{resource}?{urlencode(params)}"

        return self._result(requests.request(method=method,
                                             url=url,
                                             timeout=self.timeout))

    def _http_authenticated_request(self, method: str, resource: str, params: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        params['correlationId'] = str(uuid.uuid4())

        nonce = str(uuid.uuid4()) # requires a random, noncolliding uuid
        timestamp = str(int(time.time()))       

        digest = hmac.new(self.secret_key.encode(), str(nonce + timestamp), hashlib.sha256).digest() 
        signature = base64.b64encode(digest) 
        # signature = hmac.new(self.secret_key.encode(), url.encode(), hashlib.sha512).hexdigest()

        headers = {
            user-agent: "maker/python",
            ex-access-key: self.api_key,
            ex-access-sign: signature,
            ex-access-nonce: nonce,
            ex-access-timestamp: timestamp,
        } 

        url = f"{self.api_server}{resource}?{urlencode(params)}"

        return self._result(requests.request(method=method,
                                             url=url,
                                             headers=headers,
                                             timeout=self.timeout))

    @staticmethod
    def _result(result) -> dict:

        if not result.ok:
            raise Exception(f"eToro API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"eToro API invalid JSON response: {http_response_summary(result)}")

        return data

