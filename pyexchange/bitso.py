# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway 
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

import uuid
import hmac
import hashlib
import json

from urllib.parse import urlencode

from pyexchange.api import PyexAPI

from pymaker.numeric import Wad
from pymaker.util import http_response_summary

class Order:
    def __init__(self,
                 order_id: str,
                 timestamp: str, # current UTC time at order placement
                 book: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(book, str))
        assert(isinstance(timestamp, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.order_id = order_id
        self.timestamp = timestamp
        self.book = book
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount*self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount*self.price

    def __hash__(self):
        return hash((self.order_id,
                     self.timestamp,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_message(item):
        return Order(order_id=item['oid'],
                     timestamp=item['created_at'],
                     book=item['book'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['original_amount']))

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


class BitsoApi(PyexAPI):
    """Bitso API interface.

    Developed according to the following manual:
    <https://bitso.com/api_info>.

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

    # This endpoint returns a list of existing exchange order books and their respective order placement limits.
    def get_markets(self):
        return self._http_request("GET", "/v3/available_books", {})["payload"]

    def get_pair(self, book: str):
        assert(isinstance(book, str))
        return list(filter(lambda market: market['book'] == book, self.get_markets()))

    def get_balances(self):
        return self._http_authenticated_request("GET", "/v3/balance", {})["payload"]["balances"]

    # Trading: Retrieves a list of user's open orders
    def get_orders(self, book: str = "all", marker: str = "", sort: str = "", limit: int = 100) -> List[Order]:
        assert(isinstance(book, str))
        assert(isinstance(marker, str))
        assert(isinstance(sort, str))
        assert(isinstance(limit, int))

        # Params for filtering orders
        params = {
            "book": book, # REQUIRED: pair being traded
            "marker": marker, # OPTIONAL: order id to compare placement time against when used with sort
            "sort": sort, # OPTIONAL: sort direction of returned orders
            "limit": limit # OPtional: number or orders to return, max 100
        }

        orders = self._http_authenticated_request("GET", "/v3/open_orders", params)
        return list(map(lambda item: Order.from_message(item), orders["payload"]))

    # Trading: Submits and awaits acknowledgement of an (exclusively) limit order,
    # returning the order id.
    def place_order(self, book: str, side: str, price: float, amount: float) -> str:
        assert(isinstance(book, str))
        assert(isinstance(side, str))
        assert(isinstance(price, float))
        assert(isinstance(amount, float))

        client_id = str(uuid.uuid4())

        
        request_body = {
            "book": book, # REQUIRED
            "side": side, # REQUIRED
            "type": "limit", # REQUIRED: we exclusively trade limit orders
            "major": str(amount), # Amount of major currency being ordered
            "price": str(price), # max precision is 8 decimals
            "time_in_force": "goodtillcancelled",
            "client_id": client_id
        }

        order_type = "selllimit" if side == "sell" else "buylimit"

        self.logger.info(f"Placing order ({order_type}, amount {amount} of {book},"
                         f" price {price}), and client_id: {client_id}")

        response = self._http_authenticated_request("POST", f"/v3/orders", {}, request_body)["payload"]
        order_id = response['oid']

        self.logger.info(f"Placed order type {order_type}, order_id #{order_id}, and client_id: {client_id}")
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated_request("DELETE", f"/v3/orders/{order_id}", {})
        return result["success"]

    # Trading: Retrieves most recent trades for a given order_id or client_id.
    def get_trades(self, book: str = "", page_number: int = 1) -> List[Trade]:
        assert(isinstance(book, str))
        assert(isinstance(page_number, int))

        params = {
            "book": self._format_pair_string(book), # REQUIRED: pair being traded
            "limit": 100 # OPtional: number or orders to return, max 100
        }

        result = self._http_authenticated_request("GET", f"/v3/user_trades", params)
        return list(map(lambda item: Trade(trade_id=item['tid'],
                                           timestamp=self._iso8601_to_unix(item['created_at']),
                                           pair=item['book'],
                                           is_sell=item['side'] == 'bid',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(abs(float(item['major'])))), result["payload"]))

    def get_all_trades(self, book: str, page_number: int = 1) -> List[Trade]:
        # Params for filtering orders
        params = {
            "book": self._format_pair_string(book), # REQUIRED: pair being traded
            "limit": 100 # OPtional: number or orders to return, max 100
        }
        result = self._http_request("GET", "/v3/trades", params)["payload"]
        return list(map(lambda item: Trade(trade_id=str(item['tid']),
                                    timestamp=self._iso8601_to_unix(item['created_at']),
                                    pair=item['book'],
                                    is_sell=item['maker_side'] == 'buy',
                                    price=Wad.from_number(item['price']),
                                    amount=Wad.from_number(abs(float(item['amount'])))), result))

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

    # Interprets the response to an HTTP GET, POST or DELETE request
    def _http_authenticated_request(self, method: str, resource: str, params: dict, data: dict = {}):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))
        assert(isinstance(data, dict))

        nonce = str(int(round(time.time() * 1000)))

        # if has params, else strip out query params, otherwise call fails
        if not params:
            message = f'{nonce}{method}{resource}'
            url = f"{self.api_server}{resource}"
        else:
            message = f'{nonce}{method}{resource}?{urlencode(params)}'
            url = f"{self.api_server}{resource}?{urlencode(params)}"

        if (method == "POST"):
            message += json.dumps(data)

        signature = hmac.new(self.secret_key.encode('utf-8'),
                                            message.encode('utf-8'),
                                            hashlib.sha256).hexdigest()
        # Build the auth header
        auth_header = 'Bitso %s:%s:%s' % (self.api_key, nonce, signature)

        headers = {
            "Authorization": auth_header
        }

        if method != "POST":
            return self._result(requests.request(method=method,
                                             url=url,
                                             headers=headers,
                                             timeout=self.timeout))

        else:
            return self._result(requests.request(method=method,
                                             url=url,
                                             headers=headers,
                                             json=data,
                                             timeout=self.timeout))
    @staticmethod
    def _result(result) -> dict:

        if not result.ok:
            raise Exception(f"Bitso API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Bitso API invalid JSON response: {http_response_summary(result)}")

        return data

    # Sync trades expects pair to be structured as <Major>-<Minor>, but Bitso expects <Major>_<Minor>
    def _format_pair_string(self, pair: str) -> str:
        assert(isinstance(pair, str))
        if '-' in pair:
            return "_".join(pair.split('-')).lower()
        else:
            return pair.lower()

    def _iso8601_to_unix(self, timestamp) -> int:
        assert(isinstance(timestamp, str))
        int_timestamp = int(dateutil.parser.isoparse(timestamp).timestamp())
        return int_timestamp