# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 Exef
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
from pprint import pformat, pprint
from pyexchange.api import PyexAPI
import hmac
import hashlib
import time
import base64
import requests
import json

import dateutil.parser
from urllib.parse import urlencode

from pymaker import Address, Wad
from pymaker.util import http_response_summary
from typing import Optional, List


class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

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

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def create(item):
        return Order(order_id=item['orderId'],
                     pair=item['symbol'],
                     is_sell=True if item['side'] == 'SELL' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['origQty']))


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
    def create(pair, trade):
        return Trade(trade_id=trade['id'],
                     timestamp=trade['time'],
                     pair=pair,
                     is_sell=trade['isBuyerMaker'],
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['qty']))


class BinanceUsApi(PyexAPI):
    """Binance US API interface.

    Implemented based on https://github.com/binance-us/binance-official-api-docs/blob/master/rest-api.md
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout

    def get_balances(self):
        account_response = self._http_authenticated("GET", f"/api/v3/account", {})
        return account_response['balances']

    def get_balance(self, coin: str):
        assert(isinstance(coin, str))
        for balance in self.get_balances():
            if balance['asset'] == coin:
                return balance

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders = self._http_authenticated("GET", f"/api/v3/openOrders", {'symbol': pair})

        return [Order.create(order) for order in orders]

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        data = {
            'symbol': pair,
            'side': "SELL" if is_sell else "BUY",
            'type': 'LIMIT', 
            'quantity': float(amount),
            'price': float(price),
            'timeInForce': 'GTC'
        }

        self.logger.info(f"Placing order (Good Till Cancel, {data['side']}, amount {data['quantity']} of {pair},"
                         f" price {data['price']})...")
                         
        result = self._http_authenticated("POST", "/api/v3/order", data)
        order_id =  result['orderId']

        self.orders_for_pair[pair].append(order_id)
        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str, pair: Optional[str] = None) -> bool:
        assert(isinstance(order_id, str))
        assert(isinstance(pair, str) or (pair is None))

        if pair is None:
            raise ValueError("Pair is required")
        
        self.logger.info(f"Cancelling order #{order_id} on pair {pair}...")

        result = self._http_authenticated("DELETE", "/api/v3/order", {'orderId': order_id, 'pair': pair})

        return 'status' in result and ['status'] == "CANCELLED"
    
    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        trades_result = self._http_authenticated("GET", "/api/v3/myTrades", {'symbol': pair})

        return [Trade.create(pair, trade) for trade in trades_result]

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        
        trades_result = self._http_unauthenticated("GET", "/api/v3/trades", {'symbol': pair})

        return [Trade.create(pair, trade) for trade in trades_result]

    def _http_unauthenticated(self, method: str, resource: str, params: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             params=params,
                                             timeout=self.timeout))

    def _http_authenticated(self, method: str, resource: str, params: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        timestamp = int(round(time.time() * 1000)) 
        data = {**params, **{'timestamp': timestamp}}  

        message = urlencode(data)
        message = message.encode('ascii')
        hmac_key = self.secret_key.encode('ascii')
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_hex = signature.digest().hex()

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             params={**data, **{'signature': signature_hex}},
                                             headers={
                                                 'X-MBX-APIKEY': self.api_key,
                                             },
                                             timeout=self.timeout))

    @staticmethod
    def _result(result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Binnance API response: {http_response_summary(result)}")

        if result.content and result.content != b'OK':
            logging.debug(f"Received: {result.content}")
            try:
                data = result.json()
            except json.JSONDecodeError:
                raise ValueError(f"Binnance API invalid JSON response: {http_response_summary(result)}")
            return data
