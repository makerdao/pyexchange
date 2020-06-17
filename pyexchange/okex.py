# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2019 reverendus and EdNoepel
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
import datetime
import hmac
import json
import logging
from pprint import pformat
from typing import List

import dateutil.parser
import requests

from pyexchange.model import Candle
from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class Order:
    def __init__(self, order_id: str, timestamp: int, pair: str,
                 is_sell: bool, price: Wad, amount: Wad, filled_amount: Wad):
        assert(isinstance(order_id, str))
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
        return (self.amount - self.filled_amount)*self.price if self.is_sell else (self.amount - self.filled_amount)

    @property
    def remaining_sell_amount(self) -> Wad:
        return (self.amount - self.filled_amount) if self.is_sell else (self.amount - self.filled_amount)*self.price

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
                 trade_id: str,
                 timestamp: int,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_symbol: str):
        assert(isinstance(trade_id, str))
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

        # Only these granularities are supported by OKEX API
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

        return list(map(lambda item: Candle(timestamp=int(dateutil.parser.isoparse(item[0]).timestamp()),
                                            open=Wad.from_number(item[1]),
                                            high=Wad.from_number(item[2]),
                                            low=Wad.from_number(item[3]),
                                            close=Wad.from_number(item[4]),
                                            volume=Wad.from_number(item[5])), result))

    # Account: Get available and frozen balances for each token
    def get_balances(self) -> dict:
        result = self._http_get("/api/spot/v3/accounts", "", requires_auth=True)

        balances = {}
        for balance in result:
            balances[balance["currency"]] = balance

        return balances

    # Trading: Retrieves currently open orders, sorted newest first.
    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        result = self._http_get("/api/spot/v3/orders_pending",
                                f"&instrument_id={pair}",
                                requires_auth=True, has_cursor=False)

        return list(map(self._parse_order, result))

    # Trading: Retrieves 100 most recent orders for a particular pair, newest first, 
    # which have not been completely filled.
    def get_orders_history(self, pair: str, number_of_orders: int) -> List[Order]:
        assert(isinstance(pair, str))
        assert(isinstance(number_of_orders, int))
        assert(number_of_orders <= 100)

        result = self._http_get("/api/spot/v3/orders",
                                f"state=0&instrument_id={pair}&limit={number_of_orders}",
                                requires_auth=True, has_cursor=False)
        if len(result) > 0:
            orders = list(map(self._parse_order, result))
            # HACK: Server is not sorting properly.
            orders.sort(key=lambda order: -order.timestamp)
            return orders[:number_of_orders]
        else:
            return []

    # Trading: Submits and awaits acknowledgement of a limit order,
    # returning the order id.
    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
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
            'size': float(amount),
            'margin': 0
        })
        order_id = result['order_id']

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}) as #{order_id}")

        return order_id

    # Trading: Synchronously cancels an order.
    def cancel_order(self, pair: str, order_id: str) -> bool:
        assert(isinstance(pair, str))
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order {order_id}...")

        result = self._http_post(f"/api/spot/v3/cancel_orders/{order_id}", {
            'instrument_id': pair
        })
        # OKEX API documentation states response should contain a "result" boolean to indicate
        # success or failure.  This field was not observed during testing.  Failure is trapped
        # by a HTTP 400 response, as with other requests.
        success = result['order_id'] == order_id

        if success:
            self.logger.info(f"Cancelled order {order_id}")
        else:
            self.logger.info(f"Failed to cancel order {order_id}")

        return success

    # Trading: Retrieves most recent 100 filled or partially filled orders for a pair.
    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result_part_filled = self._http_get(f"/api/spot/v3/orders", f"state=1&instrument_id={pair}",
                                            requires_auth=True, has_cursor=False)
        result_filled = self._http_get("/api/spot/v3/orders", f"state=2&instrument_id={pair}",
                                       requires_auth=True, has_cursor=False)

        trades = list(map(lambda item: Trade(trade_id=item['order_id'],
                                             timestamp=int(dateutil.parser.isoparse(item['timestamp']).timestamp()),
                                             is_sell=item['side'] == 'sell',
                                             price=Wad.from_number(item['price']),
                                             amount=Wad.from_number(item['filled_size']),
                                             amount_symbol=item['instrument_id'].split('-')[0].lower()),
                          result_part_filled + result_filled))

        trades.sort(key=lambda trade: -trade.timestamp)
        return trades

    # Market data: Retrieves most recent 100 prints for a pair across all market participants.
    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        # TODO: Implement pagination to retrieve first 600 trades,
        # equivalent with the v1 behavior, or actually do something
        # meaningful with the page_number.
        result = self._http_get(f"/api/spot/v3/instruments/{pair}/trades",
                                f"symbol={pair}", requires_auth=False, has_cursor=False)
        return list(map(lambda item: Trade(trade_id=item['trade_id'],
                                           timestamp=int(dateutil.parser.isoparse(item['timestamp']).timestamp()),
                                           is_sell=item['side'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['size']),
                                           amount_symbol=pair.split('_')[0].lower()), result))

    @staticmethod
    def _parse_order(item: dict) -> Order:
        assert(isinstance(item, dict))
        return Order(order_id=item['order_id'],
                     timestamp=int(dateutil.parser.isoparse(item['timestamp']).timestamp()),
                     pair=item['instrument_id'],
                     is_sell=item['side'] == 'sell',
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['size']),
                     filled_amount=Wad.from_number(item['filled_size']))

    # Interprets the response to an HTTP GET or POST request
    @staticmethod
    def _result(response, check_result: bool, has_cursor=False) -> dict:
        assert(isinstance(check_result, bool))

        if not response.ok:
            raise Exception(f"OKCoin API invalid HTTP response: {http_response_summary(response)}")

        try:
            data = response.json()
        except Exception:
            raise Exception(f"OKCoin API invalid JSON response: {http_response_summary(response)}")

        # This code may be uncommented to prepare JSON samples for unit tests.
        # file = open(f"okex-response-dump-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S%f')}.json", "w")
        # file.write(json.dumps(data))
        # file.close()

        if check_result:
            if 'error_code' in data and data["error_code"] != "0" and data["error_code"] != "":
                raise Exception(f"OKCoin API negative response: {http_response_summary(response)}")

        if has_cursor:
            # FIXME: These don't return useful values
            cursor_info = {
                'before': response.headers.get('OK-BEFORE', 0),
                'after': response.headers.get('OK-AFTER', 0),
                'from': response.headers.get('OK-FROM', 0),
                'to': response.headers.get('OK-TO', 0)}
            return data #, cursor_info
        else:
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
        return headers

    def _http_get(self, resource: str, params: str,
                  check_result=True, requires_auth=False, has_cursor=False):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))
        assert(isinstance(requires_auth, bool))
        assert(isinstance(check_result, bool))

        if params:
            request = f"{resource}?{params}"
        else:
            request = resource

        return self._result(
            requests.get(url=f"{self.api_server}{request}",
                         headers=self._create_http_headers("GET", request, "") if requires_auth else None,
                         timeout=self.timeout), check_result, has_cursor)

    def _http_post(self, resource: str, params: dict, has_cursor=False):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))
        # Auth headers are required for all POST requests

        return self._result(
            requests.post(url=f"{self.api_server}{resource}",
                          data=json.dumps(params),
                          headers=self._create_http_headers("POST", resource, json.dumps(params)),
                          timeout=self.timeout), True, has_cursor)
