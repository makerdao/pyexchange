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

    def __hash__(self):
        return hash((self.order_id,
                     self.timestamp,
                     self.price,
                     self.amount))

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


class KorbitApi(PyexAPI):
    """Korbit API interface.

    Developed according to the following manual:
    <https://apidocs.korbit.co.kr/>.
    
    Authentication uses OAuth 2.0. Access tokens expire within one hour, 
    and requires refresh token to be called periodically
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, password: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(password, str))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.password = password
        self.timeout = timeout
        self.token = {}
        self.time_to_expiry = 0

    def get_balances(self):
        return self._http_authenticated_request("GET", "/user/balances", {})

    def get_markets(self):
        return self._http_unauthenticated_request("GET", "/v1/ticker/detailed/all", {})

    def get_pair(self, pair: str):
        assert(isinstance(pair, str))
        return self.get_markets()[f"{pair}"]

    # TODO: up to hurr
    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders = self._http_authenticated_request("GET", f"/orders?product_id={pair}", {})

        return list(map(lambda item: Order.from_list(item, pair), orders))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        data = {
            "size": str(amount),
            "price": str(price),
            "side": "sell" if is_sell else "buy",
            "product_id": pair
        }

        self.logger.info(f"Placing order ({data['side']}, amount {data['size']} of {pair},"
                         f" price {data['price']})...")

        result = self._http_authenticated_request("POST", "/orders", data)
        order_id = result['id']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated_request("DELETE", f"/orders/{order_id}", {})

        if order_id not in result:
            return False

        return True

    def cancel_all_orders(self) -> List:
        self.logger.info(f"Cancelling all orders ...")

        result = self._http_authenticated_request("DELETE", "/orders", {})
        success = len(result) > 0

        if success:
            self.logger.info(f"Cancelled orders : #{result}")
        else:
            self.logger.info(f"No order canceled ")

        return result

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_authenticated_request("GET", f"/fills?product_id={pair}", {})

        return list(map(lambda item: Trade.from_our_list(pair, item), result))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        limit = 100

        result = self._http_unauthenticated("GET", f"/products/{pair}/trades?before={page_number}&limit={limit}", {})

        return list(map(lambda item: Trade.from_all_list(pair, item), result))

    def get_korbit_wallets(self):
        return self._http_authenticated_request("GET", "/korbit-accounts", {})

    def get_korbit_wallet(self, coin: str):
        assert isinstance(coin, str)
        korbit_wallets = self.get_korbit_wallets()
        for wallet in korbit_wallets:
            if wallet['currency'] == coin:
                return wallet
        return None

    def get_korbit_wallet_address(self, coin: str) -> Address:
        assert isinstance(coin, str)
        wallet = self.get_korbit_wallet(coin)
        if wallet is None:
            raise ValueError(f"Wallet for {coin} not found; ensure Korbit Pro supports this token")
        wallet_id = wallet['id']
        result = self._http_authenticated_request("POST", f"/korbit-accounts/{wallet_id}/addresses", {})
        return Address(result['address'])

    def _get_access_token(self) -> str:
        # Generate access_token if keeper is being initalized for the first time
        if self.time_to_expiry == 0:
            payload = {
                "client_id": self.api_key,
                "client_secret": self.secret_key,
                "grant_type": "client_credentials"
            }
            
            response = self._result(requests.request(
                method="POST",
                url="https://api.korbit.co.kr/v1/oauth2/access_token",
                data=payload,
                timeout=self.timeout
            ))["access_token"]

            self.token["refresh_token"] = response["refresh_token"]
            self.token["access_token"] = response["access_token"]
            self.time_to_expiry = response["expires_in"]
            return self.token["access_token"]

        # use existing access_token if not near expiry
        elif self.time_to_expiry > 60:
            return self.token["access_token"]

        # call refresh token to trigger access token regeneration if within get orders timespan
        else:
            self._get_refresh_token()
            return self.token["access_token"]

    # Regenerates access, refresh, and time to expiry
    def _get_refresh_token(self):
        payload = {
            "client_id": self.api_key,
            "client_secret": self.secret_key,
            "refresh_token": self.token["refresh_token"],
            "grant_type": "refresh_token"
        }

        response = self._result(requests.request(
            method="POST",
            url="https://api.korbit.co.kr/v1/oauth2/access_token",
            data=payload,
            timeout=self.timeout
        ))

        self.token["refresh_token"] = response["refresh_token"]
        self.token["access_token"] = response["access_token"]
        self.time_to_expiry = response["expires_in"]

    def _http_authenticated_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        nonce = str(time.time()) # Nonce must be monotonically increasing

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             headers={
                                                 "Accept": "Application/JSON",
                                                 "Authorization": f"Bearer {self.token["access_token"]}"
                                             },
                                             timeout=self.timeout))

    def _http_unauthenticated_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Korbit API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Korbit API invalid JSON response: {http_response_summary(result)}")

        return data
