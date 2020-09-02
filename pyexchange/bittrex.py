# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2020 reverendus, grandizzy, Exef
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

from urllib.parse import urlencode

from pyexchange.api import PyexAPI
from pyexchange.model import Order as BaseOrder, Trade

from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class Order(BaseOrder):
    @staticmethod
    def to_order(item):
        return Order(order_id=item['id'],
                     timestamp=int(dateutil.parser.parse(item['createdAt'] + 'Z').timestamp()),
                     pair=item['marketSymbol'],
                     is_sell=True if item['direction'] == 'SELL' else False,
                     price=Wad.from_number(item['limit']),
                     amount=Wad.from_number(item['quantity']))


class BittrexApi(PyexAPI):
    """Bittrex API interface.

    Developed according to the following manual:
    <https://bittrex.github.io/api/v3>.
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
        return self._http_request("GET", "/v3/markets", {})

    def get_pair(self, pair: str):
        assert(isinstance(pair, str))
        return next(filter(lambda market: market['symbol'] == pair, self.get_markets()))

    def get_balances(self):
        return self._http_authenticated_request("GET", "/v3/balances")

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        self.logger.debug(f"Current pair: {pair}")
        orders = self._http_authenticated_request("GET", "/v3/orders/open")

        return list(map(lambda item: Order.to_order(item), 
                        filter(lambda order: order['marketSymbol'] == pair, orders)))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        body = {
            'marketSymbol': pair,
            'direction': "SELL" if is_sell else "BUY",
            'quantity': float(price),
            'limit': float(price)
        }

        self.logger.info(f"Placing order ({body['direction']}, amount {body['quantity']} of {pair},"
                         f" price {body['limit']})...")

        order_id = self._http_authenticated_request("POST", f"/v3/market/orders", body)['id']

        self.logger.info(f"Placed order type {body['direction']}, id #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated_request("DELETE", f"/v3/orders/{order_id}")

        return "closedAt" in result and result['closedAt'] is not None

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        trades = self._http_authenticated_request("GET", f"/v3/orders/closed")

        return list(map(lambda item: Trade(trade_id=item['id'],
                                           timestamp=int(dateutil.parser.parse(item['createdAt'] + 'Z').timestamp()),
                                           pair=item['marketSymbol'],
                                           is_sell=True if item['direction'] == 'SELL' else False,
                                           price=Wad.from_number(item['limit']),
                                           amount=Wad.from_number(item['fillQuantity'])), 
                        filter(lambda trade: trade['marketSymbol'] == pair, trades)))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_request("GET", f"/v3/markets/{pair}/trades", {})

        return list(map(lambda item: Trade(trade_id=item['id'],
                                           timestamp=int(dateutil.parser.parse(item['executedAt'] + 'Z').timestamp()),
                                           pair=pair,
                                           is_sell=True if item['takerSide'] == "SELL" else False,
                                           price=Wad.from_number(item['rate']),
                                           amount=Wad.from_number(item['quantity'])), 
                        result))

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

    def _http_authenticated_request(self, method: str, resource: str, body: Optional[dict] = None): 
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        timestamp = str(int(time.time() * 1000))
        content = json.dumps(body) if body else ""
        content_hash = hashlib.sha512(content.encode()).hexdigest()
        url = f"{self.api_server}{resource}"

        message = f"{timestamp}{url}{method}{content_hash}"

        signature = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha512).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "Api-Key": self.api_key,
            "Api-TimeStamp": timestamp,
            "Api-Content-Hash": content_hash,
            "Api-Signature": signature,
        }

        return self._result(requests.request(method=method,
                                             url=url,
                                             data=body,
                                             headers =headers,
                                             timeout=self.timeout))

    @staticmethod
    def _result(result) -> dict:

        if not result.ok:
            raise Exception(f"Bittrex API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Bittrex API invalid JSON response: {http_response_summary(result)}")

        return data

