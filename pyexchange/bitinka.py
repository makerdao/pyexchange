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
from pprint import pformat

from pyexchange.api import PyexAPI
from pymaker import Wad
from pymaker.util import http_response_summary
from typing import List, Optional
import dateutil.parser
import requests
import json

class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(order_id, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.order_id = order_id
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount*self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount*self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_list(item: list, pair: str):
        return Order(order_id=item['order_id'],
                     pair=pair,
                     is_sell=False if item['Type'] == 'BUY' else True,
                     price=Wad.from_number(item['Price']),
                     amount=Wad.from_number(item['Amount']))


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int) or (trade_id is None))
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
    def from_list(trade, pair):
        return Trade(trade_id=trade['trade_id'],
                     timestamp=int(dateutil.parser.parse(trade['datetime'] + 'Z').timestamp()),
                     pair=f"{trade['fromCurrency']}-{trade['toCurrency']}",
                     is_sell=True if trade['Type'] == 'SELL' else False,
                     price=Wad.from_number(trade['Price']),
                     amount=Wad.from_number(trade['Amount']))


class BitinkaApi(PyexAPI):
    """Bitinka API interface, https://www.bitinka.com/uk/bitinka/api_documentation
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float, requests_params=None):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout

    def get_markets(self):
        result = self._http_unauthenticated("GET", "/markets?format=json")
        return list(map(lambda market: market['pair'], result))

    def get_balances(self):
        return self._http_authenticated("POST", "/get_wallet_balance/format/json", {})

    def get_trade_balances(self):
        return self._http_authenticated("POST", "/get_balance/format/json", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        currencies = pair.split('-')

        data = {
            "firstCurrency": currencies[0],
            "secondCurrency": currencies[1],
            "trade": 1
        }

        result = self._http_authenticated("POST", "/orders_user/format/json", data)

        if 'status' in result and result['status'] == 'It does not have active orders':
            return []

        return list(map(lambda item: Order.from_list(item, pair), result))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        currencies = pair.split('-')

        data = {
            "new": {
                "firstCurrency": currencies[0],
                "investement": str(amount) if is_sell else str(amount * price),
                "price": str(price),
                "secondCurrency": currencies[1],
                "trade": 1,
                "typeOrder": "Sell" if is_sell else "Buy"
            }
        }

        self.logger.info(f"Placing order ({data['new']['typeOrder']}, amount {data['new']['investement']} of {pair},"
                         f" price {data['new']['price']})...")

        result = self._http_authenticated("POST", "/create_order/format/json", data)

        if 'return' in result and result['return'] is False:
            raise Exception(f"Create order failed with: {result['msg']}")

        order_id = result['idOrder']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: int) -> bool:
        assert(isinstance(order_id, int))

        self.logger.info(f"Cancelling order #{order_id}...")

        data = {
            "id": [f"{order_id}:1"]
        }

        result = self._http_authenticated("POST", f"/cancel_order/format/json", data)

        if result[0]['status'] == 'CA':
            self.logger.info(f"Cancelled order #{order_id}")
            return True

        self.logger.info(f"Failed to cancel order #{order_id}")
        return False

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        currencies = pair.split('-')

        data = {
            "firstCurrency": currencies[0],
            "secondCurrency": currencies[1],
            "trade": 1
        }

        result = self._http_authenticated("POST", f"/trade_history/format/json", data)

        if 'result' in result and result['result'] == 'user not have transactions':
            return []

        return list(map(lambda trade: Trade.from_list(trade, pair), result))

    def _http_unauthenticated(self, method: str, resource: str):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             timeout=self.timeout))

    def _http_authenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        body['key'] = self.api_key
        body['secret'] = self.secret_key

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Bitinka API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Bitinka API invalid JSON response: {http_response_summary(result)}")

        return data

