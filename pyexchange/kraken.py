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
import hmac
import hashlib
import time
import base64
import requests
import json
import threading

from pymaker import Wad
from pymaker.util import http_response_summary
from typing import Optional, List
from urllib.parse import urlencode


class Order:
    def __init__(self,
                 order_id: str,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 filled_amount: Wad):

        assert(isinstance(order_id, str))
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

    def __eq__(self, other):
        assert(isinstance(other, Order))

        return self.order_id == other.order_id and \
               self.pair == other.pair

    def __hash__(self):
        return hash((self.order_id, self.pair))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_our_order(id, order):
        return Order(id,
                     order['descr']['pair'],
                     True if order['descr']['type'] == 'sell' else False,
                     Wad.from_number(order['descr']['price']),
                     Wad.from_number(order['vol']),
                     Wad.from_number(order['vol_exec']))


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str) or (trade_id is None))
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
    def from_our_trade(id, trade):
        return Trade(trade_id=id,
                     timestamp=int(trade['time']),
                     pair=trade['pair'],
                     is_sell=True if trade['type'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['vol']))

    @staticmethod
    def from_all_response(pair, trade):
        return Trade(trade_id=None,
                     timestamp=int(trade[2]),
                     pair=pair,
                     is_sell=True if trade[3] == 's' else False,
                     price=Wad.from_number(trade[0]),
                     amount=Wad.from_number(trade[1]))


class KrakenApi(PyexAPI):
    """Kraken API interface.
    https://www.kraken.com/features/api
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout

        self.last_nonce = 0
        self.last_nonce_lock = threading.Lock()

    def get_markets(self):
        return self._http_unauthenticated("POST", "/0/public/AssetPairs", {})

    def get_assets(self):
        return self._http_unauthenticated("POST", "/0/public/Assets", {})

    def get_pair(self, pair):
        assert(isinstance(pair, str))
        return self.get_markets().get(pair)

    def get_balances(self):
        return self._http_authenticated("POST", "/0/private/Balance", {})

    def get_trade_balances(self):
        return self._http_authenticated("POST", "/0/private/TradeBalance", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        result = self._http_authenticated("POST", "/0/private/OpenOrders", {})
        orders = []

        for order_id, order in result['open'].items():
            if order['descr']['pair'] == pair and order['descr']['ordertype'] == 'limit':
                orders.append(Order.from_our_order(order_id, order))

        return orders

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        data = {
            'pair': pair,
            'type': 'sell' if is_sell else "buy",
            'ordertype': 'limit',
            "volume": str(amount),
            "price": str(price)
        }

        self.logger.info(f"Placing order ({data['type']}, amount {data['volume']} of {pair},"
                         f" price {data['price']})...")

        result = self._http_authenticated("POST", "/0/private/AddOrder", data)

        return result['txid'][0]

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")
        self._http_authenticated("POST", "/0/private/CancelOrder", {'txid': order_id})

        return True

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_authenticated("POST", f"/0/private/TradesHistory", {})

        trades = []

        for trade_id, trade in result['trades'].items():
            if trade['pair'] == pair and trade['ordertype'] == 'limit':
                trades.append(Trade.from_our_trade(trade_id, trade))

        return trades

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        result = self._http_unauthenticated("POST", f"/0/public/Trades?pair={pair}", {})

        return list(map(lambda item: Trade.from_all_response(pair, item), result[pair]))

    def _http_authenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        body['nonce'] = self._choose_nonce()
        postdata = urlencode(body)
        encoded = (str(body['nonce']) + postdata).encode()
        message = resource.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.secret_key), message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=body,
                                             headers={
                                                 'API-Key': self.api_key,
                                                 'API-Sign': sigdigest.decode()
                                             },
                                             timeout=self.timeout))

    def _http_unauthenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    def _choose_nonce(self) -> int:
        with self.last_nonce_lock:
            timed_nonce = int(time.time()*1000)

            if self.last_nonce + 1 > timed_nonce:
                self.logger.info(f"Wanted to use nonce '{timed_nonce}', but last nonce is '{self.last_nonce}'")
                self.logger.info(f"In this case using '{self.last_nonce + 1}' instead")

                self.last_nonce += 1
            else:
                self.last_nonce = timed_nonce

            return self.last_nonce

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Kraken API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Kraken API invalid JSON response: {http_response_summary(result)}")

        if data['error']:
            raise Exception(f"Kraken API error : {data['error']}")

        return data['result']
