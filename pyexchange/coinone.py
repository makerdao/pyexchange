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
import base64
import hashlib
import logging
import threading

import dateutil.parser
import hmac
import time
import requests
import json

from typing import List, Optional
from hmac import HMAC

from lib.pymaker.pymaker.util import http_response_summary
from pyexchange.api import PyexAPI
from pyexchange.model import Order, Trade
from pymaker import Wad


class CoinoneOrder(Order):

    @staticmethod
    def from_message(item: list, pair: str, market_info: dict) -> Order:
        decimal_exponent = 18 - int(market_info['quoteCurrency']['decimals'])
        price = Wad.from_number(float(item['price']) * 10**decimal_exponent)

        return Order(order_id=item['id'],
                     timestamp=int(dateutil.parser.parse(item['createdAt']).timestamp()),
                     pair=pair,
                     is_sell=True if item['side'] == 'SELL' else False,
                     price=price,
                     amount=Wad.from_number(from_wei(abs(int(float(item['baseAmount']))), 'ether')))


class CoinoneTrade(Trade):

    @staticmethod
    def from_message(trade, pair: str, market_info: dict) -> Trade:
        decimal_exponent = 18 - int(market_info['quoteCurrency']['decimals'])
        price = Wad.from_number(float(trade['price']) * 10**decimal_exponent)

        return Trade(trade_id=trade['uuid'],
                     timestamp=int(dateutil.parser.parse(trade['createdAt']).timestamp()),
                     pair=trade["market"],
                     is_sell=True if trade['side'] == 'SELL' else False,
                     price=price,
                     amount=Wad.from_number(from_wei(abs(int(float(trade['amount']))), 'ether')))


class CoinoneApi(PyexAPI):
    """Coinone API interface.

        Documentation available here: https://doc.coinone.co.kr/

    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, app_id: str, app_secret: str, access_token: str, secret_key, timeout: float):
        assert(isinstance(app_id, str))
        assert(isinstance(secret_key, str))

        self.api_server = api_server
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token
        self.secret_key = secret_key
        self.timeout = timeout
        self.token = {}
        self.last_nonce = 0
        self.last_nonce_lock = threading.Lock()

    def get_balances(self) -> dict:
        return self._http_authenticated_request("POST", "/v2/account/balance", {})

    # Doesn't retrieve precision information for the market, only orderbook info
    def get_markets(self) -> List:
        return self._http_unauthenticated_request("GET", "/orderbook", {})

    def get_pair(self, pair: str) -> List:
        assert(isinstance(pair, str))
        return list(filter(lambda market: market['currency'] == pair, self.get_markets()))

    # List keepers open orders
    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        currency = pair.split('-')[0]

        orders = self._http_authenticated_request("POST", f"/v2/order/limit_orders/", {"currency": currency})
        return list(map(lambda item: Order.from_list(item, pair), orders["limitOrders"]))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        side = "limit_buy" if is_sell == False else "limit_sell"
        currency = pair.split('-')[0]

        data = {
            "currency": currency,
            "price": price, # quote token is always krw
            "qty": str(amount
)
        }

        self.logger.info(f"Placing order ({side}, amount {data['coin_amount']} of {pair},"
                         f" price {data['price']})...")
        result = self._http_authenticated_request("POST", f"/v2/order/{side}", data)
        order_id = result['orderId']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: int, pair: str) -> bool:
        assert(isinstance(order_id, int))
        assert(isinstance(pair, str))

        self.logger.info(f"Cancelling order #{order_id}...")
        
        data = {
            "order_id": order_id,
            "price": "",
            "qty": "",
            "is_ask": "",
            "currency": pair
        }

        result = self._http_authenticated_request("POST", f"/v2/order/cancel", data)
        return True if result["result"] == "success" else False

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

    def _get_encoded_payload(self, payload) -> bytes:
        nonce = self._choose_nonce()

        payload["access_token"] = self.access_token
        payload["nonce"] = nonce

        payload = json.dumps(payload, separators=(',', ':'))
        return base64.b64encode(bytes(payload, 'utf-8'))

    def _get_signature(self, encoded_payload) -> HMAC:
        return hmac.new(bytes(self.secret_key, 'utf-8'), encoded_payload, hashlib.sha512).hexdigest()

    def _http_authenticated_request(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        url = f"{self.api_server}{resource}"

        encoded_payload = self._get_encoded_payload(body)

        headers = {
            "Accept": "Application/JSON",
            'Content-type': 'application/json',
            "X-COINONE-PAYLOAD": encoded_payload,
            "X-COINONE-SIGNATURE": self._get_signature(encoded_payload)
        }

        return self._result(requests.request(method=method,
                                             url=url,
                                             data=encoded_payload,
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
            raise Exception(f"Coinone API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Coinone API invalid JSON response: {http_response_summary(result)}")

        return data

    # Sync trades expects pair to be structured as <Major>-<Minor>, but Coinone expects <Major>_<Minor>
    def _format_pair_string(self, pair: str) -> str:
        assert(isinstance(pair, str))
        if '-' in pair:
            return "_".join(pair.split('-')).lower()
        else:
            return pair.lower()

