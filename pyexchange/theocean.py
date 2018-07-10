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
from typing import Optional

import requests

import pymaker.zrx
from pymaker import Wad, Address
from pymaker.util import http_response_summary
from pymaker.zrx import ZrxExchange


# class Order:
#     def __init__(self,
#                  order_id: int,
#                  pair: str,
#                  is_sell: bool,
#                  price: Wad,
#                  amount: Wad,
#                  amount_remaining: Wad):
#
#         assert(isinstance(order_id, int))
#         assert(isinstance(pair, str))
#         assert(isinstance(is_sell, bool))
#         assert(isinstance(price, Wad))
#         assert(isinstance(amount, Wad))
#         assert(isinstance(amount_remaining, Wad))
#
#         self.order_id = order_id
#         self.pair = pair
#         self.is_sell = is_sell
#         self.price = price
#         self.amount = amount
#         self.amount_remaining = amount_remaining
#
#     @property
#     def sell_to_buy_price(self) -> Wad:
#         return self.price
#
#     @property
#     def buy_to_sell_price(self) -> Wad:
#         return self.price
#
#     @property
#     def remaining_buy_amount(self) -> Wad:
#         return self.amount_remaining*self.price if self.is_sell else self.amount_remaining
#
#     @property
#     def remaining_sell_amount(self) -> Wad:
#         return self.amount_remaining if self.is_sell else self.amount_remaining*self.price
#
#     def __repr__(self):
#         return pformat(vars(self))
#
#
# class Trade:
#     def __init__(self,
#                  trade_id: id,
#                  timestamp: int,
#                  pair: str,
#                  is_sell: bool,
#                  price: Wad,
#                  amount: Wad,
#                  money: Wad):
#         assert(isinstance(trade_id, int))
#         assert(isinstance(timestamp, int))
#         assert(isinstance(pair, str))
#         assert(isinstance(is_sell, bool))
#         assert(isinstance(price, Wad))
#         assert(isinstance(amount, Wad))
#         assert(isinstance(money, Wad))
#
#         self.trade_id = trade_id
#         self.timestamp = timestamp
#         self.pair = pair
#         self.is_sell = is_sell
#         self.price = price
#         self.amount = amount
#         self.money = money
#
#     def __eq__(self, other):
#         assert(isinstance(other, Trade))
#         return self.trade_id == other.trade_id and \
#                self.timestamp == other.timestamp and \
#                self.pair == other.pair and \
#                self.is_sell == other.is_sell and \
#                self.price == other.price and \
#                self.amount == other.amount and \
#                self.money == other.money
#
#     def __hash__(self):
#         return hash((self.trade_id,
#                      self.timestamp,
#                      self.pair,
#                      self.is_sell,
#                      self.price,
#                      self.amount,
#                      self.money))
#
#     def __repr__(self):
#         return pformat(vars(self))


class Pair:
    def __init__(self, sell_token: Address, buy_token: Address):
        assert(isinstance(sell_token, Address))
        assert(isinstance(buy_token, Address))

        self.sell_token = sell_token
        self.buy_token = buy_token

    def __str__(self):
        return f"<{self.sell_token},{self.buy_token}>"


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

    # def get_orders(self, pair: str) -> List[Order]:
    #     assert(isinstance(pair, str))
    #
    #     per_page = 100
    #
    #     orders_open = self._http_post(f"/v0/orders?per_page={per_page}", {
    #         'market': pair,
    #         'state': 'open'
    #     })
    #
    #     orders_unfunded = self._http_post(f"/v0/orders?per_page={per_page}", {
    #         'market': pair,
    #         'state': 'unfunded'
    #     })
    #
    #     orders_unknown = self._http_post(f"/v0/orders?per_page={per_page}", {
    #         'market': pair,
    #         'state': 'unknown'
    #     })
    #
    #     if len(orders_open) >= per_page:
    #         raise Exception(f"Unable to get all 'open' orders as we are hitting the per_page={per_page} limit")
    #
    #     if len(orders_unfunded) >= per_page:
    #         raise Exception(f"Unable to get all 'unfunded' orders as we are hitting the per_page={per_page} limit")
    #
    #     if len(orders_unknown) >= per_page:
    #         raise Exception(f"Unable to get all 'unknown' orders as we are hitting the per_page={per_page} limit")
    #
    #     return list(map(lambda item: Order(order_id=int(item['id']),
    #                                        pair=pair,
    #                                        is_sell=item['type'] == 'sell',
    #                                        price=Wad.from_number(item['price']),
    #                                        amount=Wad.from_number(item['amount']),
    #                                        amount_remaining=Wad.from_number(item['amountRemaining'])),
    #                     list(orders_open) + list(orders_unfunded) + list(orders_unknown)))

    def place_order(self, pair: Pair, is_sell: bool, price: Wad, amount: Wad, fee_in_zrx: bool = False) -> int:
        assert(isinstance(pair, Pair))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(fee_in_zrx, bool))

        # `zrx_exchange` has to be present if we want to place orders
        assert(self.zrx_exchange is not None)

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        reserve_request = {'walletAddress': Address(self.zrx_exchange.web3.eth.defaultAccount).address,
                           'baseTokenAddress': pair.sell_token.address,
                           'quoteTokenAddress': pair.buy_token.address,
                           'side': 'sell' if is_sell else 'buy',
                           'orderAmount': str(amount.value),
                           'price': str(price),
                           'feeOption': 'feeInZRX' if fee_in_zrx else 'feeInNative'}

        reserve_response = self._http_authenticated("POST", "/v0/limit_order/reserve", reserve_request)

        print(json.dumps(reserve_request))
        print(reserve_response)

        # return -1

        target_order = reserve_response['unsignedTargetOrder']
        target_order['maker'] = Address(self.zrx_exchange.web3.eth.defaultAccount).address

        order = pymaker.zrx.Order.from_json(self.zrx_exchange, target_order)
        print(order.to_json())
        order = self.zrx_exchange.sign_order(order)
        xxx = order.to_json()
        xxx['orderHash'] = self.zrx_exchange.get_order_hash(order)
        print(xxx)

        place_request = {'signedTargetOrder': xxx}
        place_response = self._http_authenticated("POST", "/v0/limit_order/place", place_request)

        print(place_response)


        # signedTargetOrder

        # fee = self._calculate_fee(is_sell, price, amount, order)

        #
        # result = self._http_post_signed("/v0/order", {
        #     'exchangeContractAddress': str(order.exchange_contract_address.address),
        #     'expirationUnixTimestampSec': str(order.expiration),
        #     'feeRecipient': str(order.fee_recipient.address),
        #     'maker': str(order.maker.address),
        #     'makerFee': str(order.maker_fee.value),
        #     'makerTokenAddress': str(order.pay_token.address),
        #     'makerTokenAmount': str(order.pay_amount.value),
        #     'salt': str(order.salt),
        #     'taker': str(order.taker.address),
        #     'takerFee': str(order.taker_fee.value),
        #     'takerTokenAddress': str(order.buy_token.address),
        #     'takerTokenAmount': str(order.buy_amount.value),
        #     'v': str(order.ec_signature_v),
        #     'r': str(order.ec_signature_r),
        #     's': str(order.ec_signature_s),
        #     'feeId': reserve_response['fee']['id']
        # })
        # order_id = result['id']
        #
        # self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
        #                  f" price {price}, fee {float(fee)*100:.4f}%) as #{order_id}")

        # return order_id

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
    #
    # def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
    #     assert(isinstance(pair, str))
    #     assert(isinstance(page_number, int))
    #
    #     result = self._http_get("/v0/tradeHistory", f"market={pair}&page={page_number}&per_page=50")['trades']
    #
    #     result = filter(lambda item: item['state'] == 'confirmed', result)
    #
    #     return list(map(lambda item: Trade(trade_id=int(item['id']),
    #                                        timestamp=int(dateutil.parser.parse(item['created']).timestamp()),
    #                                        pair=pair,
    #                                        is_sell=item['type'] == 'sell',
    #                                        price=Wad.from_number(item['price']),
    #                                        amount=Wad.from_number(item['amount']),
    #                                        money=Wad.from_number(item['total'])), result))

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
        msg = bytes(self.api_key + str(timestamp) + method + data, "utf-8")
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
        timestamp = int(round(time.time()*1000))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             headers={
                                                 "Content-Type": "application/json",
                                                 "TOX-ACCESS-KEY": self.api_key,
                                                 "TOX-ACCESS-SIGN": self._create_signature(timestamp, method.upper(), data),
                                                 "TOX-ACCESS-TIMESTAMP": str(timestamp)
                                             },
                                             timeout=self.timeout))
