# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway 
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
from datetime import datetime, timezone

import io
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
                 timestamp: str, # current UTC time at order placement
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(pair, str))
        assert(isinstance(timestamp, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.order_id = order_id
        self.timestamp = timestamp
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

    def __hash__(self):
        return hash((self.order_id,
                     self.timestamp,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_message(item):
        return Order(order_id=item['id'],
                     timestamp=datetime.now(tz=timezone.utc).isoformat(), # No timestamp or created_at information is returned as part of get_orders()
                     pair=item['instrument_id'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['volume']))

class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 pair: Optional[str],
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str) or (pair is None))
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


class EToroApi(PyexAPI):
    """eToro API interface.

    Developed according to the following manual:
    <https://etorox.github.io/docs/#/>.

    Authentication requires conversion of encrypted private key with empty passphrase
    to an unencrypted private key file: openssl pkcs8 -in .etoro-key -out <unencrypted-key-file>
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, account: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(account, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, io.IOBase))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.account = account
        self.timeout = timeout
        self.api_key = api_key
        self.secret_key = secret_key.read()

    def get_markets(self):
        return self._http_authenticated_request("GET", "/api/v1/instruments", {})

    def get_pair(self, pair: str):
        assert(isinstance(pair, str))
        return list(filter(lambda market: market['name'] == pair, self.get_markets()))

    def get_balances(self):
        return self._http_authenticated_request("GET", "/api/v1/balances", {})

    def get_order(self, order_id: str):
        assert(isinstance(order_id, str))
        return self._http_authenticated_request("GET", f"/api/v1/order/{order_id}", {})

    # Trading: Retrieves 25 most recent orders for a particular pair, newest first, 
    # which have not been completely filled.
    def get_orders(self, pair: str, state: str, before: str = "", limit: int = 25) -> List[Order]:
        assert(isinstance(pair, str))
        assert(isinstance(state, str))
        assert(isinstance(before, str))
        assert(isinstance(limit, int))

        # Params for filtering orders
        params = {
            "instrument_id": pair, # REQUIRED: pair being traded
            "state": state, # REQUIRED: open, cancelled, executed
            "before": before, # OPTIONAL: latest date from which to retreive orders
            "limit": limit # OPTIONAL: number of orders to return, defaults to 25
        }

        orders = self._http_authenticated_request("GET", "/api/v1/orders", params)
        return list(map(lambda item: Order.from_message(item), orders))

    # Trading: Submits and awaits acknowledgement of a limit order,
    # returning the order id.
    def place_order(self, pair: str, side: str, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(side, str))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        request_body = {
            "instrument_id": pair,
            "side": side,
            "price": str(price),
            "volume": str(amount)
        }

        order_type = "selllimit" if side == "ask" else "buylimit"

        self.logger.info(f"Placing order ({order_type}, amount {amount} of {pair},"
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

    # Trading: Retrieves most recent 100 trades for a pair.
    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        # Params for filtering trades
        params = {
            'instrument_id': self._join_string(pair),
            'limit': 100
            # 'start': '2020-01-12T09:17:14.123321Z', # OPTIONAL: Params for recieving trades in a given window
            # 'end': '2020-01-15T09:17:14.123321Z', # OPTIONAL: Params for recieving trades in a given window
            # 'market': 'ethusdc' # OPTIONAL: Params for recieving trades in a given window
        }

        result = self._http_authenticated_request("GET", "/api/v1/trades", params)
        return list(map(lambda item: Trade(trade_id=item['trade_id'],
                                           timestamp=int(dateutil.parser.parse(item['created_at']).timestamp()),
                                           pair=item['instrument_id'],
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
        
    # Interprets the response to an HTTP GET, POST or DELETE request
    # All eToro requests other than retrieving server time require authentication
    def _http_authenticated_request(self, method: str, resource: str, params: dict, req_body: dict = {}):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))
        assert(isinstance(req_body, dict))

        params['correlationId'] = str(uuid.uuid4())

        nonce = str(uuid.uuid4())
        timestamp = str(int(round(time.time() * 1000)))

        headers = {
            "user-agent": self.account,
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

    # Sync trades expects pair to be structured as <Major>-<Minor>
    def _join_string(self, string: str) -> str:
        assert(isinstance(string, str))
        if '-' in string:
            return "".join(string.split('-')).lower()
        else:
            return string.lower()
