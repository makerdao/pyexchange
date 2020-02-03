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
import time
import requests
import json
import threading

from pymaker import Address, Wad
from pymaker.util import http_response_summary
from typing import Optional, List


class Order:
    def __init__(self,
                 order_id: int,
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
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
    def from_list(item: dict, pair: str):
        return Order(order_id=item["id"],
                     timestamp=item["timestamp"],
                     pair=pair,
                     is_sell=True if item["type"] == "ask" else False,
                     price=Wad.from_number(item["price"]["value"]),
                     amount=Wad.from_number(item["total"]["value"]))


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
        return Trade(trade_id=trade["id"],
                     timestamp=trade["completedAt"],
                     pair=pair,
                     is_sell=True if trade["type"] == "sell" else False,
                     price=Wad.from_number(trade["fillsDetail"]["price"]["value"]),
                     amount=Wad.from_number(trade["fillsDetail"]["amount"]["value"]))

    @staticmethod
    def from_all_list(pair, trade):
        return Trade(trade_id=int(trade["tid"]),
                     timestamp=trade["timestamp"],
                     pair=pair,
                     is_sell=True if trade["type"] == "sell" else False,
                     price=Wad.from_number(trade["price"]),
                     amount=Wad.from_number(trade["amount"]))


class KorbitApi(PyexAPI):
    """Korbit API interface.

    Developed according to the following manual:
    <https://apidocs.korbit.co.kr/>.
    
    Authentication uses OAuth 2.0. Access tokens expire within one hour, 
    and requires refresh token to be called periodically
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self.token = {}
        self.time_to_expiry = 0
        self.time_at_generation = 0
        self.last_nonce = 0
        self.last_nonce_lock = threading.Lock()

    def get_balances(self):
        return self._http_authenticated_request("GET", "/v1/user/balances", {})

    def get_markets(self):
        return self._http_unauthenticated_request("GET", "/v1/ticker/detailed/all", {})

    def get_pair(self, pair: str):
        assert(isinstance(pair, str))
        return self.get_markets()[f"{pair}"]

    # List keepers open orders
    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders = self._http_authenticated_request("GET", f"/v1/user/orders/open?currency_pair={pair}", {})
        return list(map(lambda item: Order.from_list(item, pair), orders))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        side = "buy" if is_sell == False else "sell"
        
        data = {
            "currency_pair": pair,
            "type": "limit",
            "price": str(price),
            "coin_amount": str(amount),
            "nonce": self._choose_nonce()
        }

        self.logger.info(f"Placing order ({side}, amount {data['coin_amount']} of {pair},"
                         f" price {data['price']})...")
        result = self._http_authenticated_request("POST", f"/v1/user/orders/{side}", data)
        order_id = result['orderId']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: int, pair: str) -> bool:
        assert(isinstance(order_id, int))
        assert(isinstance(pair, str))

        self.logger.info(f"Cancelling order #{order_id}...")
        
        data = {
            "currency_pair": pair,
            "nonce": self._choose_nonce(),
            "id": order_id
        }

        result = self._http_authenticated_request("POST", f"/v1/user/orders/cancel", data)
        if result[0]["status"] == "success":
            return True
        else:
            return False

    def get_trades(self, pair: str, offset: int = 0) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(offset, int))

        # Limit and Offset are optional, but limit is hardcoded to the maximum available 40 as opposed to default of 10
        result = self._http_authenticated_request("GET", f"/v1/user/transactions?currency_pair={self._format_pair_string(pair)}&offset={offset}&limit=40", {})

        return list(map(lambda item: Trade.from_our_list(self._format_pair_string(pair), item), result))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        period = "day" # "day, "minute, "hour"

        result = self._http_unauthenticated_request("GET", f"/v1/transactions?currency_pair={self._format_pair_string(pair)}&time={period}", {})

        # Retrieve 100 most rcent trades for a given pair, sorted by timestampd
        most_recent_trades = sorted(result, key=lambda t: t["timestamp"], reverse=True)[:100]
        return list(map(lambda item: Trade.from_all_list(pair, item), most_recent_trades))

    def _get_access_token(self) -> str:
        # check to see if enough time has elapsed since the oauth tokens were generated, with a 60 second buffer period
        if self.token:
            current_time = int(round(time.time()))
            should_refresh = self.time_to_expiry < (current_time - self.time_at_generation + 60)
        else:
            should_refresh = False

        # Generate access_token if keeper is being initalized for the first time
        if should_refresh == False and not self.token:
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
            ))

            self.token["refresh_token"] = response["refresh_token"]
            self.token["access_token"] = response["access_token"]
            self.time_to_expiry = response["expires_in"]
            self.time_at_generation = int(round(time.time())) # record unix epoch at which token was generated
            return self.token["access_token"]

        # use existing access_token if not near expiry
        elif should_refresh == False:
            return self.token["access_token"]

        # call refresh token to trigger access token regeneration if within above set timespan
        # Get orders timespan is called every 30 seconds, but 60 is used to establish a buffer
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
        self.time_at_generation = int(round(time.time())) # reset record unix epoch at which token was generated

    def _http_authenticated_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        url = f"{self.api_server}{resource}"

        access_token = self._get_access_token()
        headers = {
            "Accept": "Application/JSON",
            "Authorization": f"Bearer {access_token}",
            "content-type": "Application/JSON"
        }

        data = json.dumps(body, separators=(',', ':'))
        return self._result(requests.request(method=method,
                                             url=url,
                                             data=data,
                                             headers=headers,
                                             timeout=self.timeout))

    def _http_unauthenticated_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))
        url = f"{self.api_server}{resource}"

        return self._result(requests.request(method=method,
                                             url=url,
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

    # Sync trades expects pair to be structured as <Major>-<Minor>, but Korbit expects <Major>_<Minor>
    def _format_pair_string(self, pair: str) -> str:
        assert(isinstance(pair, str))
        if '-' in pair:
            return "_".join(pair.split('-')).lower()
        else:
            return pair.lower()

    def _choose_nonce(self) -> int:
        with self.last_nonce_lock:
            timed_nonce = int(time.time()*1000)
            time.sleep(0.1)

            if self.last_nonce + 1 > timed_nonce:
                self.logger.info(f"Wanted to use nonce '{timed_nonce}', but last nonce is '{self.last_nonce}', using '{self.last_nonce + 1}' instead")

                self.last_nonce += 1
            else:
                self.last_nonce = timed_nonce

            return self.last_nonce            