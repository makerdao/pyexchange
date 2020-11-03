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

from luno_python.client import Client
import hmac
import requests
import json
import base64
import hashlib
import datetime, time
from typing import Optional, List

from urllib.parse import urlencode

from pymaker import Address, Wad
from pymaker.util import http_response_summary
from pyexchange.api import PyexAPI
from pyexchange.model import Order, Trade


class LunoTrade(Trade):
  @staticmethod
  def from_trade(item):
    return LunoTrade(trade_id=str(item["order_id"]),
                       timestamp=int(item["timestamp"]),
                       pair=item["pair"],
                       is_sell=False if item["is_buy"] else True,
                       price=Wad.from_number(item["price"]),
                       amount=Wad.from_number(item["volume"]))

class LunoOrder(Order):
  @staticmethod
  def create(item):
    return LunoOrder(order_id=item["order_id"],
                       pair=item["symbol"].upper(),
                       is_sell=True if item["side"].lower() == "sell" else False,
                       price=Wad.from_number(item["price"]),
                       amount=Wad.from_number(item["executed_amount"]),
                       timestamp=int(item["timestamp"]))


class LunoApi(PyexAPI):
  """ Luno Exchange API interface

  Implemented based on https://www.luno.com/en/developers/api and 
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
    
    self._client = Client(api_key_id=api_key, api_key_secret=api_secret)

  def get_balances(self):
    return self._client.get_balances()

  def get_balance(self, coin: str):
    assert(isinstance(coin, str))

    return self._client.get_balances(assets=[coin])

  def get_orders(self, pair: str) -> List[LunoOrder]:
    assert(isinstance(pair, str))
    pair = self._fix_pair(pair)
    response = self._client.list_orders(pair=pair, state="PENDING")
    orders = response.get("orders", [])

    return list(map(lambda order: LunoOrder.create(order), orders))
  
  def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
    assert(isinstance(pair, str))
    assert(isinstance(is_sell, bool))
    assert(isinstance(price, Wad))
    assert(isinstance(amount, Wad))

    pair = self._fix_pair(pair)

    order_type = "ASK" if is_sell else "BID"
    response = self._client.post_limit_order(pair=pair, price=float(price), type=order_type, volume=float(amount))

    return response["order_id"]
    
  def cancel_order(self, order_id: str) -> bool:
    assert(isinstance(order_id, str))
    self.logger.info(f"Cancelling order #{order_id}...")

    response = self._client.stop_order(order_id)

    return response["success"]

  def get_trades(self, pair: str, page_number: int = 1) -> List[LunoTrade]:
    assert(isinstance(pair, str))
    assert(isinstance(page_number, int))

    pair = self._fix_pair(pair)
    response = self._client.list_user_trades(pair)
    trades = response.get("trades", [])
    return list(map(LunoTrade.from_trade, trades))

  def get_all_trades(self, pair: str, page_number: int = 1) -> List[LunoTrade]:
    assert(isinstance(pair, str))
    assert(isinstance(page_number, int))
    
    response = self._client.list_trades(pair)
    all_trades = response.get("trades", [])
    return list(map(LunoTrade.from_trade, all_trades))

  @staticmethod
  def _fix_pair(pair) -> str:
      return str.join('', pair.split('-')).lower()
