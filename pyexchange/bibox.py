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

import hashlib
import hmac
import json
import logging
from pprint import pformat
from random import random
from typing import List, Optional

import requests
import time

from pyexchange.util import sort_trades
from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class Order:
    def __init__(self,
                 order_id: int,
                 created_at: int,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_symbol: str,
                 money: Wad,
                 money_symbol: str):
        assert(isinstance(order_id, int))
        assert(isinstance(created_at, int))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_symbol, str))
        assert(isinstance(money, Wad))
        assert(isinstance(money_symbol, str))

        self.order_id = order_id
        self.created_at = created_at
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.amount_symbol = amount_symbol
        self.money = money
        self.money_symbol = money_symbol

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.money / self.amount

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.money / self.amount

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.money if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.money

    def __eq__(self, other):
        assert(isinstance(other, Order))
        return self.order_id == other.order_id and \
               self.created_at == other.created_at and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount and \
               self.amount_symbol == other.amount_symbol and \
               self.money == other.money and \
               self.money_symbol == other.money_symbol

    def __hash__(self):
        return hash((self.order_id,
                     self.created_at,
                     self.is_sell,
                     self.price,
                     self.amount,
                     self.amount_symbol,
                     self.money,
                     self.money_symbol))

    def __repr__(self):
        return pformat(vars(self))


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_symbol: str,
                 money: Wad,
                 money_symbol: str,
                 fee: Optional[Wad]):
        assert(isinstance(trade_id, int) or (trade_id is None))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_symbol, str))
        assert(isinstance(money, Wad))
        assert(isinstance(money_symbol, str))
        assert(isinstance(fee, Wad) or (fee is None))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.amount_symbol = amount_symbol
        self.money = money
        self.money_symbol = money_symbol
        self.fee = fee

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount and \
               self.amount_symbol == other.amount_symbol and \
               self.money == other.money and \
               self.money_symbol == other.money_symbol and \
               self.fee == other.fee

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount,
                     self.amount_symbol,
                     self.money,
                     self.money_symbol,
                     self.fee))

    def __repr__(self):
        return pformat(vars(self))


class BiboxApi:
    """Bibox API interface.

    Developed according to the following manual:
    <https://github.com/Biboxcom/api_reference/wiki/home_en>.
    """

    logger = logging.getLogger()

    MAX_RETRIES = 5
    MIN_RETRY_DELAY = 0.1
    MAX_RETRY_DELAY = 0.3

    def __init__(self, api_server: str, api_key: str, secret: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.secret = secret
        self.timeout = timeout

    def _request(self, path: str, cmd: dict, retry: bool, retry_count: int = MAX_RETRIES):
        assert(isinstance(path, str))
        assert(isinstance(cmd, dict))
        assert(isinstance(retry, bool))

        cmds = json.dumps([cmd])
        call = {
            "cmds": cmds,
            "apikey": self.api_key,
            "sign": self._sign(cmds)
        }

        for try_number in range(1, retry_count+1):
            result = requests.post(self.api_server + path, json=call, timeout=self.timeout)

            if retry and try_number < retry_count:
                if not result.ok:
                    self.logger.info(f"Bibox API invalid HTTP response for '{cmd['cmd']}': {http_response_summary(result)}, retrying")
                    time.sleep(self.MIN_RETRY_DELAY + random()*(self.MAX_RETRY_DELAY-self.MIN_RETRY_DELAY))
                    continue

                try:
                    if str(result.json()['error']['code']) == '4003':
                        self.logger.info(f"Bibox API busy for '{cmd['cmd']}': {http_response_summary(result)}, retrying")
                        time.sleep(self.MIN_RETRY_DELAY + random()*(self.MAX_RETRY_DELAY-self.MIN_RETRY_DELAY))
                        continue
                except:
                    pass

            if not result.ok:
                raise Exception(f"Bibox API invalid HTTP response for '{cmd['cmd']}': {http_response_summary(result)}")

            try:
                result_json = result.json()
            except Exception:
                raise Exception(f"Bibox API invalid JSON response for '{cmd['cmd']}': {http_response_summary(result)}")

            if 'error' in result_json:
                raise Exception(f"Bibox API negative response for '{cmd['cmd']}': {http_response_summary(result)}")

            return result_json['result'][0]['result']

    def _sign(self, msg: str) -> str:
        assert(isinstance(msg, str))
        return hmac.new(key=self.secret.encode('utf-8'), msg=msg.encode('utf-8'), digestmod=hashlib.md5).hexdigest()

    def ticker(self, pair: str, retry: bool = False) -> dict:
        assert(isinstance(pair, str))
        assert(isinstance(retry, bool))
        return self._request('/v1/mdata', {"cmd": "api/ticker", "body": {"pair": pair}}, retry)

    def user_info(self, retry: bool = False) -> dict:
        assert(isinstance(retry, bool))
        return self._request('/v1/user', {"cmd": "user/userInfo", "body": {}}, retry)

    def coin_list(self, retry: bool = False) -> list:
        assert(isinstance(retry, bool))
        return self._request('/v1/transfer', {"cmd": "transfer/coinList", "body": {}}, retry)

    def assets(self, retry: bool = False) -> dict:
        assert(isinstance(retry, bool))
        return self._request('/v1/transfer', {"cmd": "transfer/assets", "body": {}}, retry)

    def get_orders(self, pair: str, retry: bool = False) -> List[Order]:
        assert(isinstance(pair, str))
        assert(isinstance(retry, bool))

        result = self._request('/v1/orderpending', {"cmd": "orderpending/orderPendingList", "body": {"pair": pair,
                                                                                                     "account_type": 0,
                                                                                                     "page": 1,
                                                                                                     "size": 900}}, retry)

        # We are interested in limit orders only ("order_type":2)
        items = filter(lambda item: item['order_type'] == 2, result['items'])

        return list(map(lambda item: Order(order_id=item['id'],
                                           created_at=item['createdAt'],
                                           is_sell=True if item['order_side'] == 2 else False,
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_symbol=item['coin_symbol'],
                                           money=Wad.from_number(item['money']),
                                           money_symbol=item['currency_symbol']), items))

    def place_order(self, is_sell: bool, amount: Wad, amount_symbol: str, money: Wad, money_symbol: str, retry: bool = False) -> int:
        assert(isinstance(is_sell, bool))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_symbol, str))
        assert(isinstance(money, Wad))
        assert(isinstance(money_symbol, str))
        assert(isinstance(retry, bool))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} {amount_symbol},"
                         f" money {money} {money_symbol})...")

        order_id = self._request('/v1/orderpending', {"cmd": "orderpending/trade",
                                                      "body": {
                                                          "pair": amount_symbol + "_" + money_symbol,
                                                          "account_type": 0,
                                                          "order_type": 2,
                                                          "order_side": 2 if is_sell else 1,
                                                          "pay_bix": 0,
                                                          "price": float(money / amount),
                                                          "amount": float(amount),
                                                          "money": float(money)
                                                      }}, retry)

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} {amount_symbol},"
                         f" money {money} {money_symbol}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: int, retry: bool = False) -> bool:
        assert(isinstance(order_id, int))
        assert(isinstance(retry, bool))

        self.logger.info(f"Cancelling order #{order_id}...")
        result = self._request('/v1/orderpending', {"cmd": "orderpending/cancelTrade", "body": {"orders_id": order_id}}, retry)
        self.logger.info(f"Cancelled order #{order_id}")

        return result == "撤销中"

    def get_trades(self, pair: str, page_number: int = 1, retry: bool = False) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(isinstance(retry, bool))

        result = self._request('/v1/orderpending', {"cmd": "orderpending/orderHistoryList",
                                                    "body": {
                                                        "pair": pair,
                                                        "account_type": 0,
                                                        "page": page_number,
                                                        "size": 200
                                                    }}, retry)['items']

        # We are interested in limit orders only ("order_type":2)
        trades = list(filter(lambda item: item['order_type'] == 2, result))

        trades = list(map(lambda item: Trade(trade_id=item['id'],
                                             timestamp=int(item['createdAt']/1000),
                                             pair=pair,
                                             is_sell=True if item['order_side'] == 2 else False,
                                             price=Wad.from_number(item['price']),
                                             amount=Wad.from_number(item['amount']),
                                             amount_symbol=item['coin_symbol'],
                                             money=Wad.from_number(item['money']),
                                             money_symbol=item['currency_symbol'],
                                             fee=Wad.from_number(item['fee'])), trades))

        return sort_trades(trades)

    def get_all_trades(self, pair: str, page_number: int = 1, retry: bool = False) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)
        assert(isinstance(retry, bool))

        result = self._request('/v1/mdata', {"cmd": "api/deals",
                                                    "body": {
                                                        "pair": pair,
                                                        "size": 200
                                                    }}, retry)

        return list(map(lambda item: Trade(trade_id=None,
                                           timestamp=int(item['time']/1000),
                                           pair=pair,
                                           is_sell=True if item['side'] == 2 else False,
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_symbol=pair.split('_')[0].upper(),
                                           money=Wad.from_number(item['price']) * Wad.from_number(item['amount']),
                                           money_symbol=pair.split('_')[1].upper(),
                                           fee=None), result))

    @staticmethod
    def _trade_to_dict(trade: Trade) -> dict:
        assert(isinstance(trade, Trade))
        return {
            'trade_id': trade.trade_id,
            'timestamp': trade.timestamp,
            'pair': trade.pair,
            'is_sell': trade.is_sell,
            'price': str(trade.price),
            'amount': str(trade.amount),
            'amount_symbol': trade.amount_symbol,
            'money': str(trade.money),
            'money_symbol': trade.money_symbol,
            'fee': str(trade.fee) if trade.fee is not None else None
        }

    @staticmethod
    def _trade_from_dict(d: dict) -> Trade:
        assert(isinstance(d, dict))
        return Trade(trade_id=d['trade_id'],
                     timestamp=d['timestamp'],
                     pair=d['pair'],
                     is_sell=d['is_sell'],
                     price=Wad.from_number(d['price']),
                     amount=Wad.from_number(d['amount']),
                     amount_symbol=d['amount_symbol'],
                     money=Wad.from_number(d['money']),
                     money_symbol=d['money_symbol'],
                     fee=Wad.from_number(d['fee']) if 'fee' in d and d['fee'] is not None else None)
