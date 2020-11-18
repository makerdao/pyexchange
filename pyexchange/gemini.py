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
from logging import error

import os
import hmac
import requests
import json
import base64
import hashlib
import datetime, time

from urllib.parse import urlencode

from pymaker import Address, Wad
from pymaker.util import http_response_summary
from pyexchange.api import PyexAPI
from pyexchange.model import Order, Trade
from typing import Optional, List, Tuple


class GeminiTrade(Trade):
  @staticmethod
  def from_my_trade(pair, item):
    return GeminiTrade(trade_id=str(item["tid"]),
                       timestamp=int(item["timestamp"]),
                       pair=pair,
                       is_sell=True if item["type"].lower() == "sell" else False,
                       price=Wad.from_number(item["price"]),
                       amount=Wad.from_number(item["amount"]))

  @staticmethod
  def from_trade(pair, item):
    return GeminiTrade(trade_id=str(item["tid"]),
                       timestamp=int(item["timestamp"]),
                       pair=pair,
                       is_sell=True if item["type"].lower() == "sell" else False,
                       price=Wad.from_number(item["price"]),
                       amount=Wad.from_number(item["amount"]))

class GeminiOrder(Order):
  @staticmethod
  def create(item):
    return GeminiOrder(order_id=item["order_id"],
                       pair=item["symbol"].upper(),
                       is_sell=True if item["side"].lower() == "sell" else False,
                       price=Wad.from_number(item["price"]),
                       amount=Wad.from_number(item["remaining_amount"]),
                       timestamp=int(item["timestamp"]))


class GeminiApi(PyexAPI):
  """ Gemini Exchange API interface

  Implemented based on https://docs.gemini.com/rest-api/?python
  """

  logger = logging.getLogger()
  
  def __init__(self, api_server: str, api_key: str, api_secret: str, timeout: float) -> None:
    assert(isinstance(api_server, str))
    assert(isinstance(api_key, str))
    assert(isinstance(api_secret, str))
    assert(isinstance(timeout, float))

    self.api_server = api_server
    self.api_key = api_key
    self.api_secret = api_secret
    self.timeout = timeout
    
  def get_rules(self, pair: str) -> Tuple[Wad, Wad, Wad]:
    assert(isinstance(pair, str))
    pair = self._fix_pair(pair)
    result = self._http_unauthenticated("GET", f"/v1/symbols/details/{pair}")

    minimum_order_size =  Wad.from_number(result["min_order_size"])
    tick_size =  Wad.from_number(result["tick_size"])
    quote_currency_price_increment =  Wad.from_number(result["quote_increment"])

    return minimum_order_size, tick_size, quote_currency_price_increment


  def get_balances(self):
    balances = self._http_authenticated("POST", "/v1/balances")

    return {
      balance['currency']: {
        "amount": balance["amount"],
        "availableForTrade": balance["available"],
        "availableForWithdrawal": balance["availableForWithdrawal"]
      }
      for balance in balances
    }

  def get_balance(self, coin: str):
    assert(isinstance(coin, str))

    balances = self.get_balances()
    return balances.get(coin.upper())
    
  def get_orders(self, pair: str) -> List[GeminiOrder]:
    assert(isinstance(pair, str))
    pair = self._fix_pair(pair)

    orders = self._http_authenticated("POST", "/v1/orders")
    return list(map(lambda order: GeminiOrder.create(order), orders))
  
  def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
    assert(isinstance(pair, str))
    assert(isinstance(is_sell, bool))
    assert(isinstance(price, Wad))
    assert(isinstance(amount, Wad))

    pair = self._fix_pair(pair)

    params = {
      "symbol": pair,
      "amount": str(amount),
      "price": str(price),
      "side": "sell" if is_sell else "buy",
      "type": "exchange limit"
    }
    placed_order = self._http_authenticated("POST", "/v1/order/new", params)

    return placed_order["order_id"]

  def cancel_order(self, order_id: str) -> bool:
    assert(isinstance(order_id, str))
    self.logger.info(f"Cancelling order #{order_id}...")

    canceled_order = self._http_authenticated("POST", "/v1/order/cancel", {"order_id": order_id})

    return canceled_order["is_cancelled"]

  def get_trades(self, pair: str, page_number: int = 1) -> List[GeminiTrade]:
    assert(isinstance(pair, str))
    assert(isinstance(page_number, int))

    trades = self._http_authenticated("POST", "/v1/mytrades", {"symbol": self._fix_pair(pair)})
    return list(map(lambda trade: GeminiTrade.from_my_trade(pair, trade), trades))

  def get_all_trades(self, pair: str, page_number: int = 1) -> List[GeminiTrade]:
    assert(isinstance(pair, str))
    assert(isinstance(page_number, int))
    
    all_trades = self._http_unauthenticated("GET", f"/v1/trades/{self._fix_pair(pair)}")

    return list(map(lambda trade: GeminiTrade.from_trade(pair, trade), all_trades))

  def _http_unauthenticated(self, method: str, resource: str):
    assert(isinstance(method, str))
    assert(isinstance(resource, str))

    return self._result(requests.request(method=method,
                                         url=f"{self.api_server}{resource}",
                                         timeout=self.timeout))
    
   
  def _http_authenticated(self, method: str, resource: str, params: dict = None):
    assert(isinstance(method, str))
    assert(isinstance(resource, str))
    assert(isinstance(params, dict) or (params is None))

    if params is None:
      params = {}

    t = datetime.datetime.now()
    payload_nonce =  str(int(time.mktime(t.timetuple())*1000))

    payload = {**params, **{
      "request": resource,
      "nonce": payload_nonce,
    }}

    encoded_api_secret = self.api_secret.encode()
    encoded_payload = json.dumps(payload).encode()
    payload_b64 = base64.b64encode(encoded_payload)
    signature = hmac.new(encoded_api_secret, payload_b64, hashlib.sha384).hexdigest()

    request_headers = { 'Content-Type': "text/plain",
                        'Content-Length': "0",
                        'X-GEMINI-APIKEY': self.api_key,
                        'X-GEMINI-PAYLOAD': payload_b64,
                        'X-GEMINI-SIGNATURE': signature,
                        'Cache-Control': "no-cache" }

    return self._result(requests.request(method=method,
                                         url=f"{self.api_server}{resource}",
                                         headers=request_headers,
                                         timeout=self.timeout))
    

  @staticmethod
  def _fix_pair(pair) -> str:
      return str.join('', pair.split('-')).lower()

  @staticmethod
  def _result(result) -> Optional[dict]:
    if not result.ok:
      raise RuntimeError(f"Gemini API response: {http_response_summary(result)}")

    logging.debug(f"Received: {result.text}")
    try:
      data = result.json()
    except json.JSONDecodeError as ex:
      logging.error(result)
      logging.error(ex)
      raise ValueError(f"Gemini API invalid JSON response: {http_response_summary(result)}")
    return data


    