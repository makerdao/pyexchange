# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus
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
import hmac
import json
import logging
from pprint import pformat
from typing import List

import requests
import time

from pyexchange.model import Candle
from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(order_id, int))
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


class Trade:
    def __init__(self,
                 trade_id: id,
                 timestamp: int,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int))
        assert(isinstance(timestamp, int))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))


class EthfinexApi:
    """Ethfinex/Bitfinex API interface.

    Developed according to the following manual:
    <https://bitfinex.readme.io/v2/reference>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, api_secret: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(api_secret, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

    def candles(self, pair: str, timeframe: str, limit: int) -> List[Candle]:
        assert(isinstance(pair, str))
        assert(isinstance(timeframe, str))
        assert(isinstance(limit, int))

        assert(timeframe in ('1m', '5m', '15m', '30m', '1h', '3h', '6h', '12h',
                             '1D', '7D', '14D', '1M'))

        result = self._http_get(f"/v2/candles/trade:{timeframe}:t{pair}/hist", f"limit={limit}")

        return list(map(lambda item: Candle(timestamp=int(item[0]/1000),
                                            open=Wad.from_number(item[1]),
                                            close=Wad.from_number(item[2]),
                                            high=Wad.from_number(item[3]),
                                            low=Wad.from_number(item[4]),
                                            volume=Wad.from_number(item[5])), result))

    def get_balances(self):
        return self._http_post("/v1/balances", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        result = self._http_post(f"/v2/auth/r/orders/t{pair}", {})
        result = list(filter(lambda item: item[8] == 'EXCHANGE LIMIT', result))
        result = list(filter(lambda item: item[13] != 'CANCELED', result))

        orders = list(map(lambda item: Order(order_id=int(item[0]),
                                             pair=str(item[3][1:]).upper(),
                                             is_sell=Wad.from_number(item[6]) < Wad(0),
                                             price=Wad.from_number(item[16]),
                                             amount=abs(Wad.from_number(item[6]))), result))

        orders = list(filter(lambda order: order.pair == pair, orders))

        return orders

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> int:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        result = self._http_post("/v1/order/new", {
            "symbol": pair,
            "amount": str(amount),
            "price": str(price),
            "exchange": "bitfinex",
            "side": "sell" if is_sell else "buy",
            "type": "exchange limit"
        })
        order_id = int(result['id'])

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: int) -> bool:
        assert(isinstance(order_id, int))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_post(f"/v1/order/cancel", {"order_id": order_id})
        success = result['id'] == order_id

        if success:
            self.logger.info(f"Cancelled order #{order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}")

        return success

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_post(f"/v1/mytrades", {"symbol": pair, "limit_trades": 250})

        trades = list(map(lambda item: Trade(trade_id=int(item['tid']),
                                             timestamp=int(float(item['timestamp'])),
                                             is_sell=item['type'].upper() == 'SELL',
                                             price=Wad.from_number(item['price']),
                                             amount=Wad.from_number(item['amount'])), result))

        return trades

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_get(f"/v2/trades/t{pair}/hist", f"limit=500")
        return list(map(lambda item: Trade(trade_id=int(item[0]),
                                           timestamp=int(item[1]/1000),
                                           is_sell=(Wad.from_number(item[2]) < Wad(0)),
                                           price=Wad.from_number(item[3]),
                                           amount=abs(Wad.from_number(item[2]))), result))

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"Ethfinex API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Ethfinex API invalid JSON response: {http_response_summary(result)}")

        return data

    def _prepare_headers_v1(self, request_path: str, request_params: dict):
        assert(isinstance(request_path, str))
        assert(isinstance(request_params, dict))

        nonce = self.get_nonce()
        payload = {**{"request": request_path, "nonce": nonce}, **request_params}
        payload_encoded = base64.b64encode(bytes(json.dumps(payload), "utf-8"))

        return {
            "X-BFX-APIKEY": self.api_key,
            "X-BFX-SIGNATURE": self._create_signature(payload_encoded),
            "X-BFX-PAYLOAD": payload_encoded
        }

    def _prepare_headers_v2(self, request_path: str, request_body: str):
        assert(isinstance(request_path, str))
        assert(isinstance(request_body, str))

        nonce = self.get_nonce()
        msg = bytes("/api" + request_path + nonce + request_body, "utf-8")

        return {
            "bfx-apikey": self.api_key,
            "bfx-signature": self._create_signature(msg),
            "bfx-nonce": nonce
        }

    @staticmethod
    def get_nonce():
        return str(int(time.time() * 1000))

    def _create_signature(self, msg: bytes):
        assert(isinstance(msg, bytes))

        key = bytes(self.api_secret, "utf-8")
        signature = hmac.new(key, msg, hashlib.sha384)

        return signature.digest().hex()

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        if resource.startswith("/v1"):
            return self._result(requests.post(url=f"{self.api_server}{resource}",
                                              headers=self._prepare_headers_v1(resource, params),
                                              timeout=self.timeout))
        else:
            data = json.dumps(params)

            return self._result(requests.post(url=f"{self.api_server}{resource}",
                                              data=data,
                                              headers={
                                                  **self._prepare_headers_v2(resource, data),
                                                  **{"Content-Type": "application/json"}
                                              },
                                              timeout=self.timeout))
