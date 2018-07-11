# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 reverendus
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
import time
from pprint import pformat
from typing import Optional, List

import requests

import pymaker.zrx
from pymaker import Wad, Address
from pymaker.util import http_response_summary
from pymaker.zrx import ZrxExchange


class Pair:
    def __init__(self, sell_token: Address, buy_token: Address):
        assert(isinstance(sell_token, Address))
        assert(isinstance(buy_token, Address))

        self.sell_token = sell_token
        self.buy_token = buy_token

    def __str__(self):
        return f"<{self.sell_token},{self.buy_token}>"

    def __repr__(self):
        return pformat(vars(self))


class Order:
    def __init__(self,
                 order_id: str,
                 pair: Pair,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(order_id, str))
        assert(isinstance(pair, Pair))
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
                 trade_id: str,
                 timestamp: int,
                 pair: Pair,
                 is_sell: Optional[bool],
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, Pair))
        assert(isinstance(is_sell, bool) or (is_sell is None))
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


class TheOceanApi:
    """The Ocean API interface.

    Developed according to the following manual:
    <https://docs.theocean.trade/>.
    """

    logger = logging.getLogger()

    def __init__(self, zrx_exchange: ZrxExchange, api_server: str, api_key: str, api_secret: str, timeout: float):
        assert(isinstance(zrx_exchange, ZrxExchange) or (zrx_exchange is None))
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(api_secret, str))
        assert(isinstance(timeout, float))

        self.zrx_exchange = zrx_exchange
        self.api_server = api_server
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

    def ticker(self, pair: Pair):
        assert(isinstance(pair, Pair))
        return self._http_get_unauthenticated("/v0/ticker", f"baseTokenAddress={pair.sell_token}&"
                                                            f"quoteTokenAddress={pair.buy_token}")

    def get_balance(self, token: Address) -> Wad:
        assert(isinstance(token, Address))

        our_address = Address(self.zrx_exchange.web3.eth.defaultAccount)

        response = self._http_authenticated("GET", "/v0/available_balance?" + f"walletAddress={our_address.address}&"
                                                                              f"tokenAddress={token.address}", {})

        return Wad(int(response['availableBalance']))

    def get_orders(self, pair: Pair) -> List[Order]:
        assert(isinstance(pair, Pair))

        orders = self._http_authenticated("GET", "/v0/user_history?openAmount=1", {})

        # filter orders by our pair
        orders = list(filter(lambda item: Address(item['baseTokenAddress']) == pair.sell_token and
                                          Address(item['quoteTokenAddress']) == pair.buy_token, orders))

        return list(map(lambda item: Order(order_id=item['orderHash'],
                                           pair=pair,
                                           is_sell=item['side'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad(int(item['openAmount'])) + Wad(int(item['reservedAmount']))), orders))

    def place_order(self, pair: Pair, is_sell: bool, price: Wad, amount: Wad, fee_in_zrx: bool = False) -> Optional[str]:
        assert(isinstance(pair, Pair))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(fee_in_zrx, bool))

        # `zrx_exchange` has to be present if we want to place orders
        assert(self.zrx_exchange is not None)

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        our_address = Address(self.zrx_exchange.web3.eth.defaultAccount)

        reserve_request = {'walletAddress': our_address.address,
                           'baseTokenAddress': pair.sell_token.address,
                           'quoteTokenAddress': pair.buy_token.address,
                           'side': 'sell' if is_sell else 'buy',
                           'orderAmount': str(amount.value),
                           'price': str(price),
                           'feeOption': 'feeInZRX' if fee_in_zrx else 'feeInNative'}
        self.logger.debug(f"Limit order reserve request: {json.dumps(reserve_request, indent=None)}")

        reserve_response = self._http_authenticated("POST", "/v0/limit_order/reserve", reserve_request)
        self.logger.debug(f"Limit order reserve response: {json.dumps(reserve_response, indent=None)}")

        place_request = {}

        if 'unsignedTargetOrder' in reserve_response:
            place_request['signedTargetOrder'] = self._sign_order(reserve_response['unsignedTargetOrder'], our_address)

        if 'unsignedMarketOrder' in reserve_response and 'marketOrderID' in reserve_response:
            place_request['signedMarketOrder'] = self._sign_order(reserve_response['unsignedMarketOrder'], our_address)
            place_request['marketOrderID'] = reserve_response['marketOrderID']

        self.logger.debug(f"Limit order place request: {json.dumps(place_request, indent=None)}")

        place_response = self._http_authenticated("POST", "/v0/limit_order/place", place_request)
        self.logger.debug(f"Limit order place response: {json.dumps(place_response, indent=None)}")

        order_id = place_response.get('targetOrder', {}).get('orderHash')

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}) as #{order_id}")

        return order_id

    def _sign_order(self, order: dict, our_address) -> dict:
        assert(isinstance(order, dict))
        assert(isinstance(our_address, Address))

        order = pymaker.zrx.Order.from_json(self.zrx_exchange, {**order, 'maker': our_address.address})
        order = self.zrx_exchange.sign_order(order)

        return {**order.to_json(), 'orderHash': self.zrx_exchange.get_order_hash(order)}

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated("DELETE", f"/v0/order/#{order_id}", {})
        success = len(result) > 0

        if success:
            self.logger.info(f"Cancelled order #{order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}")

        return success

    # def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
    #     assert(isinstance(pair, str))
    #     assert(isinstance(page_number, int))
    #
    #     result = self._http_post("/v0/trades", {
    #         'market': pair,
    #         'page': page_number,
    #         'per_page': 100
    #     })['trades']
    #
    #     result = filter(lambda item: item['state'] == 'confirmed', result)
    #
    #     trades = list(map(lambda item: Trade(trade_id=int(item['id']),
    #                                          timestamp=int(dateutil.parser.parse(item['createdAt']).timestamp()),
    #                                          pair=pair,
    #                                          is_sell=item['type'] == 'sell',
    #                                          price=Wad.from_number(item['price']),
    #                                          amount=Wad.from_number(item['amount']),
    #                                          money=Wad.from_number(item['amount'])*Wad.from_number(item['price'])), result))
    #
    #     return sort_trades(trades)

    def get_all_trades(self, pair: Pair, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, Pair))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_get_unauthenticated("/v0/trade_history", f"baseTokenAddress={pair.sell_token}&"
                                                                     f"quoteTokenAddress={pair.buy_token}")

        result = filter(lambda item: item['status'] == 'settled', result)

        return list(map(lambda item: Trade(trade_id=item['id'],
                                           timestamp=int(item['lastUpdated']),
                                           pair=pair,
                                           is_sell=None,
                                           price=Wad.from_number(item['price']),
                                           amount=Wad(int(item['amount']))), result))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"TheOcean API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"TheOcean API invalid JSON response: {http_response_summary(result)}")

        return data

    def _create_signature(self, timestamp: int, method: str, data: str) -> str:
        assert(isinstance(timestamp, int))
        assert(isinstance(method, str))
        assert(isinstance(data, str))

        key = bytes(self.api_secret, "utf-8")
        msg = bytes(self.api_key + str(timestamp) + method.upper() + data, "utf-8")
        signature = hmac.new(key, msg, hashlib.sha256).digest()

        return base64.b64encode(signature)

    def _http_get_unauthenticated(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         timeout=self.timeout))

    def _http_authenticated(self, method: str, resource: str, params: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        data = json.dumps(params, separators=(',', ':'))
        timestamp = int(time.time()*1000)

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             headers={
                                                 "Content-Type": "application/json",
                                                 "TOX-ACCESS-KEY": self.api_key,
                                                 "TOX-ACCESS-SIGN": self._create_signature(timestamp, method, data),
                                                 "TOX-ACCESS-TIMESTAMP": str(timestamp)
                                             },
                                             timeout=self.timeout))
