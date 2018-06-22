# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 bargst
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

import json
import logging
import time
from pprint import pformat
from typing import List, Optional
from datetime import datetime, timezone

import requests

from pyexchange.api import PyexAPI, StreamAPI
from pyexchange.util import sort_trades
from pymaker.numeric import Wad
from pymaker.util import http_response_summary


def hitbtc_date_to_timestamp(date: str) -> float:
    # '2018-06-01T14:20:50.497Z'
    dt = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
    return dt.replace(tzinfo=timezone.utc).timestamp()


class Order:
    def __init__(self, order_id: str, status: str, timestamp: float, pair: str,
                 is_sell: bool, price: Wad, amount: Wad, filled_amount: Wad):
        assert(isinstance(order_id, str))
        assert(isinstance(status, str))
        assert(isinstance(timestamp, float))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(filled_amount, Wad))

        self.order_id = order_id
        self.status = status
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
        remaining_amount = self.amount - self.filled_amount
        return remaining_amount*self.price if self.is_sell else remaining_amount

    @property
    def remaining_sell_amount(self) -> Wad:
        remaining_amount = self.amount - self.filled_amount
        return remaining_amount if self.is_sell else remaining_amount*self.price

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
                 order_id: Optional[int],
                 timestamp: float,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int))
        assert(isinstance(order_id, str) or (order_id is None))
        assert(isinstance(timestamp, float))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.trade_id = trade_id
        self.order_id = order_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.order_id == other.order_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.order_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_dict(pair, trade):
        #{'id': 304542084, 'price': '0.077357', 'quantity': '0.013', 'side': 'sell', 'timestamp': '2018-06-01T15:30:04.132Z'}
        return Trade(trade_id=trade['id'],
                     order_id=trade.get('clientOrderId'),
                     timestamp=hitbtc_date_to_timestamp(trade['timestamp']),
                     pair=trade['symbol'] if 'symbol' in trade else pair,
                     is_sell=trade['side'] == 'sell',
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['quantity']))

class HitBTCApi(PyexAPI):
    """HitBTC API interface.

    Developed according to the following manual:
    <https://github.com/hitbtc-com/hitbtc-api>.

    Inspired by the following example:
    <https://github.com/hitbtc-com/hitbtc-api/blob/master/example_rest.py>.
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
        return self._http_get(f"/api/2/public/ticker/{pair}")

    def get_markets(self):
        return self._http_get(f"/api/2/public/symbol")

    def get_pair(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get(f"/api/2/public/symbol/{pair}")

    def get_balances(self):
        return list(filter(lambda balance: balance['available'] != '0'
                                        or balance['reserved']  != '0',
                           self._auth_get("/api/2/trading/balance")))

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        result = self._auth_get("/api/2/order")
        result = filter(lambda item: item['symbol'] == pair, result)

        return list(map(lambda item: Order(order_id=item['clientOrderId'],
                                           status=item['status'],
                                           timestamp=hitbtc_date_to_timestamp(item['createdAt']),
                                           pair=item['symbol'],
                                           is_sell=item['side'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['quantity']),
                                           filled_amount=Wad.from_number(item['cumQuantity'])), result))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        data = {
            'symbol': pair,
            'side': 'sell' if is_sell else 'buy',
            'quantity': float(amount),
            'price': float(price),
        }

        self.logger.info(f"Placing order ({data['side']}, amount {data['quantity']} of {pair},"
                         f" price {data['price']})...")

        url = "/api/2/order"
        result = self._auth_post(url, data)
        order_id = result['clientOrderId']

        self.logger.info(f"Placed order ({result['side']}, amount {result['quantity']} of {result['symbol']},"
                         f" price {result['price']}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str):
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._auth_delete(f"/api/2/order/{order_id}")
        success = result['status'] == 'canceled'

        if success:
            self.logger.info(f"Cancelled order #{order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}")

        return success

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        page_number = page_number - 1 # page offset start at 0
        per_page = 100
        page_filter = f"symbol={pair}&limit={per_page}&offset={page_number}"
        result = self._auth_get(f"/api/2/history/trades?{page_filter}")

        trades = list(map(lambda item: Trade.from_dict(pair, item), result))

        return sort_trades(trades)

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        page_number = page_number - 1 # page offset start at 0
        per_page = 100
        page_filter = f"limit={per_page}&offset={page_number}"
        result = self._http_get(f"/api/2/public/trades/{pair}?{page_filter}")

        return list(map(lambda item: Trade.from_dict(pair, item), result))

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"HitBTC API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"HitBTC API invalid JSON response: {http_response_summary(result)}")

        if 'error' in data:
            raise Exception(f"HitBTC API error response: {http_response_summary(result)}")

        return data

    def _http(self, req_func,  resource, params = None, auth = False):
        assert(callable(req_func))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        auth_tuple = None
        if auth:
            auth_tuple = (self.api_key, self.secret_key)

        return self._result(req_func(url=f"{self.api_server}{resource}",
                                     data=params,
                                     auth=auth_tuple,
                                     timeout=self.timeout))

    def _http_get(self, resource: str):
        return self._http(requests.get, resource)

    def _auth_get(self, resource: str):
        return self._http(requests.get, resource, auth=True)

    def _http_post(self, resource: str, params: dict):
        return self._http(requests.post, resource, params)

    def _auth_post(self, resource: str, params: dict):
        return self._http(requests.post, resource, params, auth=True)

    def _auth_delete(self, resource: str):
        return self._http(requests.delete, resource, auth=True)


class HitBTCStreamApi(StreamAPI):
    """HitBTC Stream API interface.

    Developed according to the following manual:
    <https://github.com/hitbtc-com/hitbtc-api#socket-api-reference>
    """

    def __init__(self, loop, ws_url, pairs):
        self.pairs = pairs
        super().__init__(loop, ws_url)

    async def subscribe(self, websocket):
        subscribe_req = {
            'method': 'subscribeTrades',
            'params': { 'symbol': None },
            'id': time.time()
        }
        for pair in self.pairs:
            subscribe_req['params']['symbol'] = pair
            await websocket.send(json.dumps(subscribe_req))

    async def get(self):
        msg = await super().get()

        if 'params' not in msg:
            return []

        params = msg['params']
        if msg.get('method') == 'updateTrades' or msg.get('method') == 'snapshotTrades':
            if 'symbol' in params and 'data' in params:
                pair = params['symbol']
                trades = [Trade.from_dict(pair, trade) for trade in params['data']]
                return trades
        else:
            return []
