# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2019 MikeHathaway 
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
                 instrument_id: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 remaining_amount: Wad):

        assert(isinstance(instrument_id, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(remaining_amount, Wad))

        self.order_id = order_id
        self.instrument_id = instrument_id
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
                     instrument_id=item['Exchange'],
                     is_sell=True if item['OrderType'] == 'LIMIT_SELL' else False,
                     price=Wad.from_number(item['Limit']),
                     amount=Wad.from_number(item['Quantity']),
                     remaining_amount=Wad.from_number(item['QuantityRemaining']))


class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 instrument_id: Optional[str],
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(instrument_id, str) or (instrument_id is None))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.instrument_id = instrument_id
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.instrument_id == other.instrument_id and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.instrument_id,
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

    def get_pair(self, instrument_id: str):
        assert(isinstance(instrument_id, str))
        return next(filter(lambda symbol: symbol['MarketName'] == instrument_id, self.get_markets()))

    def get_balances(self):
        return self._http_authenticated_request("GET", "/api/v1/balances", {})['result']

    def get_orders(self, instrument_id: str, limit: int, state: str, before: str) -> List[Order]:
        assert(isinstance(instrument_id, str))
        assert(isinstance(limit, int))
        assert(isinstance(state, str))
        assert(isinstance(before, str))

        # optional params for filtering orders
        params = {
            "instrument_id": instrument_id,
            "state": state, # open, cancelled, executed
            "limit": limit, # number of orders to return, defaults to 25
            "before": before # latest date from which to retreive orders
        }

        orders = self._http_authenticated_request("GET", "/api/v1/orders", params)['result']

        return list(map(lambda item: Order.to_order(item), orders))

    def place_order(self, instrument_id: str, side: str, price: Wad, amount: Wad) -> str:
        assert(isinstance(instrument_id, str))
        assert(isinstance(side, str))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        request_body = {
            "instrument_id": instrument_id,
            "side": side,
            "price": str(price),
            "volume": str(amount)
        }

        order_type = "selllimit" if side == "ask" else "buylimit"

        self.logger.info(f"Placing order ({order_type}, amount {params['quantity']} of {instrument_id},"
                         f" price {params['rate']})...")

        response = self._http_authenticated_request("POST", f"/api/v1/orders", params, request_body)

        if response['success'] is False:
            raise Exception(f"eToro Failed to place order {response['message']}")

        order_id = response['result']['id']

        self.logger.info(f"Placed order type {order_type}, id #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated_request("DELETE", "/api/v1/orders/{order_id}", {})

        return result['success']

    def get_trades(self, instrument_id: str, before: str, limit: int = 25) -> List[Trade]:
        assert(isinstance(instrument_id, str))
        assert(isinstance(before, str))
        assert(isinstance(page_number, int))

        # optional params
        params = {
            'instrument_id': instrument_id
            'before': before,
            'limit': limit
        }

        result = self._http_authenticated_request("GET", "/api/v1/trades", params)['result']

        return list(map(lambda item: Trade(trade_id=item['trade_id'],
                                           timestamp=int(dateutil.parser.parse(item['created_at']).timestamp()),
                                           instrument_id=item['instrument_id'],
                                           is_sell=item['side'] == 'bid',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['volume'])), result))

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

        def _http_authenticated_request(self, method: str, resource: str, params: dict, req_body: dict = {}):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))
        assert(isinstance(req_body, dict))

        params['correlationId'] = str(uuid.uuid4())

        nonce = str(int(time.time())) 
        timestamp = str(int(time.time()))       

        digest = hmac.new(self.secret_key.encode(), str(nonce + timestamp), hashlib.sha256).hexdigest() 
        signature = base64.b64encode(digest) 

        headers = {
            "user-agent": "maker-lp",
            "ex-access-key": self.api_key,
            "ex-access-sign": signature,
            "ex-access-nonce": nonce,
            "ex-access-timestamp": timestamp,
        } 

        url = f"{self.api_server}{resource}?{urlencode(params)}"

        if method != "POST":
            return self._result(requests.request(method=method,
                                             url=url,
                                             headers=headers,
                                             timeout=self.timeout))

        else:
            return self._result(requests.request(method=method,
                                             url=url,
                                             headers=headers,
                                             data=req_body,
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

