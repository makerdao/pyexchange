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

import hashlib
import logging
import requests
import json
import time

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
    def to_order(pair: str, item):
        return Order(order_id=item['orderid'],
                     pair=pair,
                     is_sell=True if item['type'] == 'sell-limit' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['orderquantity']),
                     filled_amount=Wad.from_number(item['filledquantity']))


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
    def to_trade(pair: str, trade):
        return Trade(trade_id=trade['tradeId'],
                     timestamp=int(float(trade['time'])) // 1000,
                     pair=pair,
                     is_sell=trade['take'] == 'sell',
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['quantity']))


class CoinbeneApi(PyexAPI):
    """Coinbene API interface.

    Inspired fromn Coinbene API Python 3.0 demo:
    <https://github.com/Coinbene/API-Demo-Python/>.
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

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_request("GET", f"/v1/market/ticker?symbol={pair}", {})['ticker']

    def get_markets(self):
        return self._http_request("GET", "/v1/market/symbol", {})['symbol']

    def get_pair(self, pair):
        assert(isinstance(pair, str))
        return next(filter(lambda symbol: symbol['ticker'] == pair, self.get_markets()))

    def get_balances(self):

        data = {
            "apiid": self.api_key,
            "secret": self.secret_key,
            "timestamp": self._create_timestamp(),
            "account": "exchange"
        }

        return self._http_signed_request("POST", "/v1/trade/balance", data)['balance']

    def get_orders(self, pair):
        assert(isinstance(pair, str))

        data = {
            "apiid": self.api_key,
            "secret": self.secret_key,
            "timestamp": self._create_timestamp(),
            "symbol": pair
        }

        result = self._http_signed_request("POST", "/v1/trade/order/open-orders", data)

        if result['orders'] is None:
            return []

        return list(map(lambda item: Order.to_order(pair, item), result['orders']['result']))

    def place_order(self, pair, is_sell, price, amount):
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        data = {
            "apiid": self.api_key,
            "secret": self.secret_key,
            "timestamp": self._create_timestamp(),
            "type": "sell-limit" if is_sell else "buy-limit",
            "price": str(price),
            "quantity": str(amount),
            "symbol": pair
        }

        self.logger.info(f"Placing order ({data['type']}, amount {data['quantity']} of {pair},"
                         f" price {data['price']})...")

        result = self._http_signed_request("POST", "/v1/trade/order/place", data)
        order_id = result['orderid']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id):
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        data = {
            "apiid": self.api_key,
            "secret": self.secret_key,
            "timestamp": self._create_timestamp(),
            "orderid": order_id
        }

        result = self._http_signed_request("POST", "/v1/trade/order/cancel", data)

        if order_id == result['orderid']:
            self.logger.info(f"Cancelled order #{order_id}")
            return True

        self.logger.info(f"Failed to cancel order #{order_id}")
        return False

    def get_trades(self, pair, page_number: int = 1):
        raise NotImplementedError()

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        result = self._http_request("GET", f"/v1/market/trades?symbol={pair}", {})

        return list(map(lambda item: Trade.to_trade(pair, item), result['trades']))

    @staticmethod
    def _sign(**kwargs):
        sign_list = []
        for key, value in kwargs.items():
            sign_list.append("{}={}".format(key, value))
        sign_list.sort()
        sign_str = "&".join(sign_list)
        mysecret = sign_str.upper().encode()
        m = hashlib.md5()
        m.update(mysecret)
        return m.hexdigest()

    @staticmethod
    def _create_timestamp():
        timestamp = int(round(time.time() * 1000))
        return timestamp

    def _http_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    def _http_signed_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        mysign = self._sign(**body)
        del body['secret']
        body['sign'] = mysign

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             headers={
                                                 "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko",
                                                 "Content-Type":"application/json;charset=utf-8",
                                                 "Connection":"keep-alive"
                                             },
                                             timeout=self.timeout))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Coinbene API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Coinbene API invalid JSON response: {http_response_summary(result)}")

        if data['status'] and data['status'] == 'error':
            raise Exception(f"Coinbene API error: {http_response_summary(result)}")

        return data
