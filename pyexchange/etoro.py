# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2019 MikeHathaway 
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

import uuid
import base64

from urllib.parse import urlencode

from pyexchange.api import PyexAPI

from pymaker.numeric import Wad
from pymaker.util import http_response_summary

from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

class Order:
    def __init__(self,
                 order_id: str,
                 timestamp: int, # time in seconds
                 instrument_id: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 remaining_amount: Wad):

        assert(isinstance(instrument_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(remaining_amount, Wad))

        self.order_id = order_id
        self.timestamp = timestamp
        self.instrument_id = instrument_id
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.remaining_amount = remaining_amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.remaining_amount*self.price if self.is_sell else self.remaining_amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.remaining_amount if self.is_sell else self.remaining_amount*self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def to_order(item):
        return Order(order_id=item['id'],
                     timestamp=int(time.time()), # No timestamp or created at information is returned as part of get_orders()
                     instrument_id=item['instrument_id'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['volume']),
                     remaining_amount=Wad.from_number(float(item['origin_volume']) - float(item['volume'])))


class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 instrument_id: Optional[str],
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(instrument_id, str) or (instrument_id is None))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.instrument_id = instrument_id
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.instrument_id == other.instrument_id and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.instrument_id,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))


class EToroApi(PyexAPI):
    """eToro API interface.

    Developed according to the following manual:
    <https://etorox.github.io/dxocs/#/>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.timeout = timeout
        self.api_key = api_key

        ## Need to convert encrypted private key with empty passphrase to an unencrypted private key file
        # openssl pkcs8 -in .etoro-key -out <unencrypted-key-file>
        self.secret_key = secret_key

    def get_markets(self):
        return self._http_authenticated_request("GET", "/api/v1/instruments", {})

    def get_pair(self, instrument_id: str):
        assert(isinstance(instrument_id, str))
        return list(filter(lambda market: market['name'] == instrument_id, self.get_markets()))

    def get_balances(self):
        return self._http_authenticated_request("GET", "/api/v1/balances", {})

    def get_order(self, order_id: str):
        assert(isinstance(order_id, str))
        return self._http_authenticated_request("GET", f"/api/v1/order/{order_id}", {})

    def get_orders(self, instrument_id: str,  before: str = "", state: str = "", limit: int = 25) -> List[Order]:
        assert(isinstance(instrument_id, str))
        assert(isinstance(before, str))
        assert(isinstance(state, str))
        assert(isinstance(limit, int))

        # optional params for filtering orders
        params = {
            "instrument_id": instrument_id,
            "before": before, # latest date from which to retreive orders
            "state": state, # open, cancelled, executed
            "limit": limit # number of orders to return, defaults to 25
        }

        orders = self._http_authenticated_request("GET", "/api/v1/orders", params)
        return list(map(lambda item: Order.to_order(item), orders))

    def place_order(self, instrument_id: str, side: str, price: Wad, amount: Wad) -> str:
        assert(isinstance(instrument_id, str))
        assert(isinstance(side, str))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        request_body = {
            "instrument_id": instrument_id,
            "side": side,
            "price": str(price),
            "volume": str(amount)
        }

        order_type = "selllimit" if side == "ask" else "buylimit"

        self.logger.info(f"Placing order ({order_type}, amount {amount} of {instrument_id},"
                         f" price {price})...")

        response = self._http_authenticated_request("POST", f"/api/v1/orders", {}, request_body)
        order_id = response['id']

        self.logger.info(f"Placed order type {order_type}, id #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated_request("DELETE", f"/api/v1/orders/{order_id}", {})
        return result

    def get_trades(self, instrument_id: str, before: str = "", limit: int = 25) -> List[Trade]:
        assert(isinstance(instrument_id, str))
        assert(isinstance(before, str))
        assert(isinstance(limit, int))

        # optional params
        params = {
            'instrument_id': instrument_id,
            'before': before,
            'limit': limit
        }

        result = self._http_authenticated_request("GET", "/api/v1/trades", params)
        return list(map(lambda item: Trade(trade_id=item['trade_id'],
                                           timestamp=int(dateutil.parser.parse(item['created_at']).timestamp()),
                                           instrument_id=item['instrument_id'],
                                           is_sell=item['side'] == 'bid',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['volume'])), result))

    def get_deposit_address(self, coin: str):
        assert(isinstance(coin, str))
        result = self._http_authenticated_request("GET", f"/api/v1/funds/deposits/{coin}/address", {})

        return result['address']

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

    def _generate_signature(self, nonce: str, timestamp: str):
        assert(isinstance(nonce, str))
        assert(isinstance(timestamp, str))
                
        message = f"{nonce}{timestamp}".encode('utf-8')
        hashed_message = SHA256.new(message)

        # Need to import key string as RSA Key
        private_key = RSA.importKey(self.secret_key)

        # sign hashed message with RSA private key, and then base64 encode it
        # API Doc: https://legrandin.github.io/pycryptodome/Doc/3.4.6/Crypto.Signature.pkcs1_15-module.html
        return base64.b64encode(pkcs1_15.new(private_key).sign(hashed_message))
        
    def _http_authenticated_request(self, method: str, resource: str, params: dict, req_body: dict = {}):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))
        assert(isinstance(req_body, dict))

        params['correlationId'] = str(uuid.uuid4())

        nonce = str(uuid.uuid4())
        timestamp = str(int(time.time() * 1000))

        headers = {
            "user-agent": "mm@liquidityproviders.io",
            "ex-access-key": self.api_key,
            "ex-access-sign": self._generate_signature(nonce, timestamp),
            "ex-access-nonce": nonce,
            "ex-access-timestamp": timestamp
        } 

        url = f"{self.api_server}{resource}?{urlencode(params)}"

        if method != "POST":
            return self._result(requests.request(method=method,
                                             url=url,
                                             headers=headers,
                                             timeout=self.timeout))

        else:
            return self._result(requests.request(method=method,
                                             url=url,
                                             headers=headers,
                                             data=req_body,
                                             timeout=self.timeout))
    @staticmethod
    def _result(result) -> dict:

        if not result.ok:
            raise Exception(f"eToro API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"eToro API invalid JSON response: {http_response_summary(result)}")

        return data

