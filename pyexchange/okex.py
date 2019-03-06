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

import logging
from pprint import pformat
from typing import List

import base64
import datetime
import dateutil.parser
import hmac
import json
import math
import urllib
import requests

from pyexchange.model import Candle
from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class Order:
    def __init__(self, order_id: int, timestamp: int, pair: str,
                 is_sell: bool, price: Wad, amount: Wad, filled_amount: Wad):
        assert(isinstance(order_id, int))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(filled_amount, Wad))

        self.order_id = order_id
        self.timestamp = timestamp
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
        return (self.amount - self.deal_amount)*self.price if self.is_sell else (self.amount - self.deal_amount)

    @property
    def remaining_sell_amount(self) -> Wad:
        return (self.amount - self.deal_amount) if self.is_sell else (self.amount - self.deal_amount)*self.price

    def __eq__(self, other):
        assert(isinstance(other, Order))

        return self.order_id == other.order_id and \
               self.pair == other.pair

    def __hash__(self):
        return hash((self.order_id, self.pair))

    def __repr__(self):
        return pformat(vars(self))


class Trade:
    def __init__(self,
                 trade_id: id,
                 timestamp: int,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_symbol: str):
        assert(isinstance(trade_id, int))
        assert(isinstance(timestamp, int))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_symbol, str))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.amount_symbol = amount_symbol

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount and \
               self.amount_symbol == other.amount_symbol

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.is_sell,
                     self.price,
                     self.amount,
                     self.amount_symbol))

    def __repr__(self):
        return pformat(vars(self))


class OKEXApi:
    """OKCoin and OKEX API interface.
    Developed according to the following manual:
    <https://www.okex.com/intro_apiOverview.html>.

    Inspired by the following example:
    <https://github.com/OKCoin/rest>, <https://github.com/OKCoin/rest/tree/master/python>.

    Updated to OKEX v3 API using the following specs: <https://www.okex.com/docs/en/>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str,
                 password: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(password, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.password = password
        self.timeout = timeout

    # Market data: Retrieves level-one data for the pair
    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get(f"/api/spot/v3/instruments/{pair}/ticker", "")

    # Market data: Retrieves entire depth of order book
    def depth(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get(f"/api/spot/v3/instruments/{pair}/book", "")

    # Market data: Retrieves most recent 200 time-series data points
    def candles(self, pair: str, granularity: str) -> List[Candle]:
        assert(isinstance(pair, str))
        assert(isinstance(granularity, str))

        # Note only these granularities are supported by OKEX API
        granularity_in_seconds = {
            "1min": 60,
            "3min": 180,
            "5min": 300,
            "15min": 900,
            "30min": 1800,
            "1day": 3600*24,
            "3day": 3600*24*3,
            "1week": 3600*24*7,
            "1hour": 3600,
            "2hour": 3600*2,
            "4hour": 3600*4,
            "6hour": 3600*6,
            "12hour": 3600*12
        }
        assert(granularity in granularity_in_seconds)

        result = self._http_get(f"/api/spot/v3/instruments/{pair}/candles",
                                f"granularity={granularity_in_seconds[granularity]}")

        return list(map(lambda item: Candle(timestamp=int(dateutil.parser.parse(item[0]).timestamp()),
                                            open=Wad.from_number(item[1]),
                                            high=Wad.from_number(item[2]),
                                            low=Wad.from_number(item[3]),
                                            close=Wad.from_number(item[4]),
                                            volume=Wad.from_number(item[5])), result))

    # Account: Get available and frozen balances for each token
    def get_balances(self) -> dict:
        result = self._http_get("/api/account/v3/wallet", "")

        balances = {}
        for balance in result:
            balances[balance["currency"]] = balance

        return balances

    # Trading: Retrieves currently open orders, sorted newest first.
    # Optionally filter by pair and limit number of results returned.
    def get_orders(self, pair='', number_of_orders=100) -> List[Order]:
        assert(isinstance(pair, str))
        assert(isinstance(number_of_orders, int))

        orders = []
        pages = math.ceil(number_of_orders/100)
        for page in range(1, pages):
            result = self._http_get("/api/spot/v3/orders_pending",
                                    f"from={page}&to={page+1}"
                                    f"&instrument_id={pair}")
            if len(result) > 0:
                orders += list(filter(self._parse_order(), result))

        return orders[:number_of_orders]

    # Trading: Retrieves order list for a particular pair, newest first.
    def get_orders_history(self, pair: str, number_of_orders: int) -> List[Order]:
        assert(isinstance(pair, str))
        assert(isinstance(number_of_orders, int))

        # TODO: Implement optional status filter
        #assert(status in ("all", "open", "part_filled", "canceling", "filled",
        #                  "cancelled", "ordering", "failure"))

        orders = []
        pages = math.ceil(number_of_orders/100)
        for page in range(1, pages):
            result = self._http_get("/api/spot/v3/orders",
                                    f"status=all"
                                    f"&instrument_id={pair}"
                                    f"&from={page}&to={page+1}")
            if len(result) > 0:
                orders += list(filter(self._parse_order(), result))

        return orders[:number_of_orders]

    # Submits and awaits acknowledgement of a limit order, returning the order id.
    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> int:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        result = self._http_post("/api/spot/v3/orders", {
            'instrument_id': pair,
            'type': 'limit',
            'side': 'sell' if is_sell else 'buy',
            'price': float(price),
            'size': float(amount)
        })
        order_id = int(result['order_id'])

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}) as #{order_id}")

        return order_id

    # Synchronously cancels an order.
    def cancel_order(self, pair: str, order_id: str) -> bool:
        assert(isinstance(pair, str))
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order {order_id}...")

        result = self._http_post(f"/api/spot/v3/cancel_orders/{order_id}", {
            'instrument_id': pair
        })
        success = int(result['order_id']) == order_id

        if success:
            self.logger.info(f"Cancelled order {order_id}")
        else:
            self.logger.info(f"Failed to cancel order {order_id}")

        return success

    # TODO: Seems this is now supported through /api/spot/v3/instruments/<instrument_id>/trades;
    # add support for pagination and wire it up.
    def get_trades(self, pair: str, page_number: int = 1):
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        raise Exception("get_trades() not available for OKEX")

    # TODO: Map this to /api/spot/v3/instruments/<instrument_id>/trades
    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_get("/api/v1/trades.do", f"symbol={pair}", False)
        return list(map(lambda item: Trade(trade_id=item['tid'],
                                           timestamp=item['date'],
                                           is_sell=item['type'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_symbol=pair.split('_')[0].lower()), result))

    @staticmethod
    def _parse_order(item: dict) -> Order:
        assert(isinstance(item, dict))
        return Order(order_id=item['order_id'],
                     timestamp=int(item['create_date']/1000),
                     pair=item['symbol'],
                     is_sell=item['side'] == 'sell',
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['size']),
                     filled_amount=Wad.from_number(item['filled_size']))

    # TODO: Adjust the error messages
    # Handles the response of an HTTP GET or POST request
    @staticmethod
    def _result(result, check_result: bool) -> dict:
        assert(isinstance(check_result, bool))

        if not result.ok:
            raise Exception(f"OKCoin API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"OKCoin API invalid JSON response: {http_response_summary(result)}")

        if check_result:
            if result.status_code is not 200:
                raise Exception(f"OKCoin API negative response: {http_response_summary(result)}")

            # TODO: See if any calls returns these fields in the JSON
            if 'error_code' in data:
                raise Exception(f"OKCoin API negative response: {http_response_summary(result)}")
            # if 'result' not in data or data['result'] is not True:
            #     raise Exception(f"OKCoin API negative response: {http_response_summary(result)}")

        return data

    def _create_signature(self, timestamp, method, request_path, body):
        assert(isinstance(timestamp, str))
        assert(method in ["GET", "POST"])
        assert(isinstance(request_path, str))
        assert(isinstance(body, str))

        message = str(timestamp) + method + request_path + body

        digest = hmac.new(bytes(self.secret_key, encoding="utf-8"),
                          bytes(message, encoding="utf-8"),
                          digestmod="sha256").digest()

        #print(f"message is {message}")
        return base64.b64encode(digest)

    def _create_http_headers(self, method, request_path, body):
        assert(method in ["GET", "POST"])
        assert(isinstance(request_path, str))
        assert(isinstance(body, str))

        # OKEX expects this variation of ISO 8601
        timestamp = datetime.datetime.utcnow().isoformat()[:-3] + "Z"

        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": self._create_signature(timestamp, method, request_path, body),
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.password
        }
        #print(f"url: {request_path}")
        #print(f"headers: {headers}")
        return headers

    def _http_get(self, resource: str, params: str, check_result: bool = True):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))
        assert(isinstance(check_result, bool))

        if params:
            request = f"{resource}?{params}"
        else:
            request = resource

        #print(f"HTTP GET {request}")
        return self._result(
            requests.get(url=f"{self.api_server}{request}",
                         headers=self._create_http_headers("GET", request, ""),
                         timeout=self.timeout), check_result)

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        #print(f"HTTP POST {resource} {json.dumps(params)}")
        return self._result(
            requests.post(url=f"{self.api_server}{resource}",
                          data=json.dumps(params),
                          headers=self._create_http_headers("POST", resource, json.dumps(params)),
                          timeout=self.timeout), True)
