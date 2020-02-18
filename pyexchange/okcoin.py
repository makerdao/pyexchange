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
from pyexchange.api import PyexAPI
from pyexchange.okex import OKEXApi
import hmac
import hashlib
import time
import base64
import requests
import json

import dateutil.parser

from pymaker import Address, Wad
from pymaker.util import http_response_summary
from typing import Optional, List


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


class OkcoinApi(OKEXApi):
    """Okcoin API interface.

    Inherits methods from OkEx API which is part of the same company.

    Developed according to the following manuals:
    <https://www.okcoin.com/docs/en/#>.
    <https://github.com/okcoin-okex/open-api-v3-sdk/blob/master/okex-python-sdk-api/okex/client.py>

    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, password: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(password, str))

        super().__init__(api_server, api_key, secret_key, password, timeout)

    def get_markets(self, pair: str):
        return self._http_unauthenticated_request("GET", f"/api/spot/v3/instruments", {})


    def get_deposit_address(self, currency: str = "eth") -> str:
        return self._http_get(f"/api/account/v3/deposit/address", f"currency={currency}", requires_auth=True, has_cursor=False)

    # Transfer funds from Funding Wallet to Spot Trading Account
    def transfer_funds(self, currency: str, amount: Wad) -> bool:
        data = {
            "amount": str(amount),
            "currency": currency,
            "from": 6, # Wallet Account
            "to": 1 # Spot Account
        }

        transfer = self._http_authenticated_request("POST", f"/api/account/v3/transfer", data)

        return transfer["result"]

    # return base64 encoding of a signed auth message
    def _generate_signature(self, message):
        signature = hmac.new(bytes(self.secret_key, encoding='utf8'), bytes(message, encoding='utf8'), digestmod='sha256')
        return base64.b64encode(signature.digest())

    def _generate_timestamp(self) -> str:
        now = datetime.datetime.now()
        t = now.isoformat("T", "milliseconds")
        return t + "Z"

    def _http_authenticated_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        message = ''.join([self._generate_timestamp(), method, resource, data or ''])
        # message = message.encode('ascii')

        headers = {
            'Content-Type': 'Application/JSON',
            'OK_ACCESS_KEY': self.api_key,
            'OK_ACCESS_SIGN': self._generate_signature(message),
            'OK_ACCESS_TIMESTAMP': timestamp,
            'OK_ACCESS_PASSPHRASE': self.password
        }

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             headers=headers,
                                             timeout=self.timeout), True, False)

    def _http_unauthenticated_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout), True, False)
