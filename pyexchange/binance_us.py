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
    def from_list(item: list, pair: str):
        return Order(order_id=item['id'],
                     pair=item['product_id'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['size']))


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
    def from_our_list(pair, trade):
        return Trade(trade_id=trade['trade_id'],
                     timestamp=int(dateutil.parser.parse(trade['created_at']).timestamp()),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['size']))

    @staticmethod
    def from_all_list(pair, trade):
        return Trade(trade_id=trade['trade_id'],
                     timestamp=int(dateutil.parser.parse(trade['time']).timestamp()),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['size']))


class BinanceUsApi(PyexAPI):
    """Binance US API interface.
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
        raise NotImplementedError()

    def get_balance(self, coin: str):
        assert(isinstance(coin, str))
        raise NotImplementedError()


    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders = self._http_authenticated("GET", f"/api/v3/openOrders", {'symbol': pair})

        return orders

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        raise NotImplementedError()

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))
        raise NotImplementedError()

    def cancel_all_orders(self) -> List:
        self.logger.info(f"Cancelling all orders ...")
        raise NotImplementedError()

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        raise NotImplementedError()

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        raise NotImplementedError()

    def _http_authenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        timestamp = int(round(time.time() * 1000)) 
        data = {**body, **{'timestamp': timestamp}}  

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
                raise ValueError(f"Coinbase API invalid JSON response: {http_response_summary(result)}")
            return data
