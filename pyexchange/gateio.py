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
import logging
import urllib
import hmac
from pprint import pformat
from typing import List

import requests

from pymaker.numeric import Wad


class Order:
    def __init__(self, order_id: int, timestamp: int, pair: str,
                 is_sell: bool, price: Wad, amount: Wad, amount_symbol: str,
                 money: Wad, money_symbol: str, initial_amount: Wad, filled_amount: Wad):
        assert(isinstance(order_id, int))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_symbol, str))
        assert(isinstance(money, Wad))
        assert(isinstance(money_symbol, str))
        assert(isinstance(initial_amount, Wad))
        assert(isinstance(filled_amount, Wad))

        self.order_id = order_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.amount_symbol = amount_symbol
        self.money = money
        self.money_symbol = money_symbol
        self.initial_amount = initial_amount
        self.filled_amount = filled_amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_sell_amount(self) -> Wad:
        #TODO
        pass
        #return (self.amount - self.deal_amount) if self.is_sell else (self.amount - self.deal_amount)*self.price

    def __eq__(self, other):
        assert(isinstance(other, Order))

        return self.order_id == other.order_id and \
               self.pair == other.pair

    def __hash__(self):
        return hash((self.order_id, self.pair))

    def __repr__(self):
        return pformat(vars(self))


class GateIOApi:
    """Gate.io API interface.

    Developed according to the following manual:
    <https://gate.io/api2>.

    Inspired by the following example:
    <https://github.com/gateio/rest/tree/master/python>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get("/api2/1/ticker", pair)

    def order_book(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get("/api2/1/orderBook", pair)

    def all_trade_history(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get("/api2/1/tradeHistory", pair)

    # output is: {'result': 'true', 'available': {'AAA': '0.0064128', 'BBB': '0.02'}, 'locked': {'AAA': '0.0135872'}}
    def get_balances(self):
        return self._http_post("/api2/1/private/balances", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        result = self._http_post("/api2/1/private/openOrders", {})['orders']
        result = filter(lambda item: item['currencyPair'] == pair, result)

        return list(map(lambda item: Order(order_id=int(item['orderNumber']),
                                           timestamp=int(item['timestamp']),
                                           pair=item['currencyPair'],
                                           is_sell=item['type'] == 'sell',
                                           price=Wad.from_number(item['rate']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_symbol=item['currencyPair'].split('_')[0],
                                           money=Wad.from_number(item['total']),
                                           money_symbol=item['currencyPair'].split('_')[1],
                                           initial_amount=Wad.from_number(item['initialAmount']),
                                           filled_amount=Wad.from_number(item['filledAmount'])), result))

    def get_order(self, pair: str, order_id: int):
        assert(isinstance(pair, str))
        assert(isinstance(order_id, int))
        return self._http_post("/api2/1/private/getOrder", {'orderNumber': order_id, 'currencyPair': pair})

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> int:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        url = "/api2/1/private/sell" if is_sell else "/api2/1/private/buy"
        result = self._http_post(url, {'currencyPair': pair, 'rate': float(price), 'amount': float(amount)})

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})")

        return result['orderNumber']

    def cancel_order(self, pair: str, order_id: int):
        assert(isinstance(pair, str))
        assert(isinstance(order_id, int))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_post("/api2/1/private/cancelOrder", {'orderNumber': order_id, 'currencyPair': pair})
        success = result['message'] == 'Success'

        if success:
            self.logger.info(f"Cancelled order #{order_id}...")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}...")

        return success

    def cancel_all_orders(self, pair: str) -> bool:
        assert(isinstance(pair, str))

        result = self._http_post("/api2/1/private/cancelAllOrders", {'type': -1, 'currencyPair': pair})
        return result['message'] == 'Success'

    def get_trade_history(self, pair: str):
        #TODO add trade parsing
        assert(isinstance(pair, str))
        return self._http_post("/api2/1/private/tradeHistory", {'currencyPair': pair})

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}/{params}", timeout=self.timeout))

    @staticmethod
    def _result(result) -> dict:
        data = result.json()

        if 'result' not in data or data['result'] not in [True, 'true']:
            raise Exception(f"Negative Gate.io response: {data}")

        return data

    def _create_signature(self, params):
        assert(isinstance(params, dict))

        sign = ''
        for key in (params.keys()):
            sign += key + '=' + str(params[key]) + '&'
        sign = sign[:-1]

        return hmac.new(key=bytes(self.secret_key, encoding='utf8'),
                        msg=bytes(sign, encoding='utf8'),
                        digestmod=hashlib.sha512).hexdigest()

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                          data=urllib.parse.urlencode(params),
                                          headers={"Content-Type": "application/x-www-form-urlencoded",
                                                   "KEY": self.api_key,
                                                   "SIGN": self._create_signature(params)},
                                          timeout=self.timeout))
