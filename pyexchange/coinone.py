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

import hmac
import time
import requests
import json

from json import JSONDecodeError
from typing import List, Optional
from hmac import HMAC

from lib.pymaker.pymaker.util import http_response_summary
from pyexchange.api import PyexAPI
from pyexchange.model import Order, Trade
from pymaker import Wad


class CoinoneOrder(Order):

    @staticmethod
    def from_message(item: list, pair: str) -> Order:
        return Order(order_id=item['orderId'],
                     timestamp=int(item['timestamp']),
                     pair=pair,
                     is_sell=True if item['type'] == 'ask' else False,
                     price=Wad.from_number(float(item["price"])),
                     amount=Wad.from_number(float(item['qty'])))


class CoinoneTrade(Trade):

    @staticmethod
    def from_message(trade, pair: str) -> Trade:
        return Trade(trade_id=trade['orderId'],
                     timestamp=int(trade['timestamp']),
                     pair=pair,
                     is_sell=True if trade['type'] == 'ask' else False,
                     price=Wad.from_number(float(trade["price"])),
                     amount=Wad.from_number(float(trade['qty'])))


class CoinoneApi(PyexAPI):
    """Coinone API interface.

        Documentation available here: https://doc.coinone.co.kr/

        Precision requirement information available here: https://coinone.co.kr/support/guide
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, access_token: str, secret_key: str, timeout: float = 9.5):
        assert (isinstance(api_server, str))
        assert (isinstance(access_token, str))
        assert (isinstance(secret_key, str))
        assert (isinstance(timeout, float))

        self.api_server = api_server
        self.access_token = access_token
        self.secret_key = secret_key
        self.timeout = timeout
        self.last_nonce = 0
        self.last_nonce_lock = threading.Lock()

    def get_balances(self) -> dict:
        return self._http_authenticated_request("POST", "/v2/account/balance", {})

    # Doesn't retrieve precision information for the market, only orderbook info
    def get_markets(self) -> List:
        return self._http_unauthenticated_request("GET", "/orderbook", {})

    def get_pair(self, pair: str) -> List:
        assert (isinstance(pair, str))
        return list(filter(lambda market: market['currency'] == pair, self.get_markets()))

    # List keepers open orders
    def get_orders(self, pair: str) -> List[Order]:
        assert (isinstance(pair, str))

        currency = pair.split('-')[0]

        orders = self._http_authenticated_request("POST", f"/v2/order/limit_orders/", {"currency": currency})
        return list(map(lambda item: CoinoneOrder.from_message(item, pair), orders["limitOrders"]))

    # Calculate the asking price units for a given price range
    def _calc_price_precision(self, price: float) -> int:
        assert (isinstance(price, float))

        if price < 1:
            return 0.0001
        elif 1 <= price < 10:
            return 0.001
        elif 10 <= price < 100:
            return 0.01
        elif 100 <= price < 1000:
            return 0.1
        elif 1000 <= price < 5000:
            return 1
        elif 5000 <= price < 10000:
            return 5
        elif 10000 <= price < 50000:
            return 10
        elif 50000 <= price < 100000:
            return 50
        elif 100000 <= price < 500000:
            return 100
        elif 500000 <= price < 1000000:
            return 500
        elif 1000000 <= price:
            return 1000

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, Wad))
        assert (isinstance(amount, Wad))

        side = "limit_buy" if is_sell is False else "limit_sell"
        currency = pair.split('-')[0]

        # Coinone krw price precision must be specified based upon a given range
        float_price = Wad.__float__(price)
        price_prec = self._calc_price_precision(float_price)
        price = round(round(float_price / price_prec, 0) * price_prec, 0)

        data = {
            "currency": currency,
            "price": str(price),
            "qty": str(round(Wad.__float__(amount), 2))
        }

        self.logger.info(f"Placing order ({side}, amount {data['qty']} of {pair},"
                         f" price {data['price']})...")
        response = self._http_authenticated_request("POST", f"/v2/order/{side}", data)

        order_id = ""

        if response['result'] == 'success':
            order_id = response['orderId']
            self.logger.info(f"Placed order (#{order_id})")

        return order_id

    def cancel_order(self, order_id: str, pair: str, price: Wad, amount: Wad, is_sell: bool) -> bool:
        assert (isinstance(order_id, str))
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, Wad))
        assert (isinstance(amount, Wad))

        self.logger.info(f"Cancelling order #{order_id}...")

        currency = pair.split('-')[0]
        is_ask = 1 if is_sell is True else 0

        data = {
            "order_id": order_id,
            "currency": currency,
            "price": str(round(Wad.__float__(price), 2)),  # quote token is always krw
            "qty": str(round(Wad.__float__(amount), 2)),
            "is_ask": is_ask
        }

        result = self._http_authenticated_request("POST", f"/v2/order/cancel", data)
        return True if result["result"] == "success" else False

    def get_trades(self, pair: str, offset: int = 0) -> List[Trade]:
        assert (isinstance(pair, str))
        assert (isinstance(offset, int))

        currency = pair.split('-')[0]

        result = self._http_authenticated_request("POST", f"/v2/order/complete_orders", {"currency": currency})
        return list(map(lambda item: CoinoneTrade.from_message(item, pair), result['completeOrders']))

    def _choose_nonce(self) -> int:
        with self.last_nonce_lock:
            timed_nonce = int(time.time() * 1000)

            if self.last_nonce + 1 > timed_nonce:
                self.logger.info(
                    f"Wanted to use nonce '{timed_nonce}', but last nonce is '{self.last_nonce}', using '{self.last_nonce + 1}' instead")

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
        assert (isinstance(method, str))
        assert (isinstance(resource, str))
        assert (isinstance(body, dict) or (body is None))

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
        assert (isinstance(method, str))
        assert (isinstance(resource, str))
        assert (isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))
        url = f"{self.api_server}{resource}"

        return self._result(requests.request(method=method,
                                             url=url,
                                             data=data,
                                             timeout=self.timeout))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Coinone API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except (RuntimeError, JSONDecodeError):
            raise ValueError(f"Coinone API invalid JSON response: {http_response_summary(result)}")

        return data

