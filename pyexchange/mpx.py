# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 grandizzy
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
import requests
import json
from pymaker import Wad, Address
from pymaker.util import http_response_summary
from typing import Optional, List
from pyexchange.zrxv2 import Pair
from pymaker.sign import eth_sign
from pymaker.zrxv2 import ZrxExchangeV2, ERC20Asset
import datetime


class MpxPair(Pair):

    def __init__(self, pair: str, sell_token_address, sell_token_decimals, buy_token_address, buy_token_decimals):
        assert(isinstance(pair, str))

        super().__init__(sell_token_address, sell_token_decimals, buy_token_address, buy_token_decimals)
        self.pair_name = pair

    def get_pair_name(self):
        return self.pair_name


class Order:
    def __init__(self,
                 order_id: str,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, Wad))
        assert (isinstance(amount, Wad))

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
        return self.amount * self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount * self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_list(item: list, pair: MpxPair):

        maker_amount = Wad(int(item['attributes']['maker-asset-amount']))
        taker_amount = Wad(int(item['attributes']['taker-asset-amount']))

        is_sell = pair.sell_token_address == ERC20Asset.deserialize(item['attributes']['maker-asset-data']).token_address
        price = taker_amount / maker_amount if is_sell else maker_amount / taker_amount
        amount = maker_amount if is_sell else taker_amount

        return Order(order_id=item['id'],
                     pair=item['attributes']['pair-name'],
                     is_sell=is_sell,
                     price=price,
                     amount=amount)


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str) or (trade_id is None))
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
    def from_list(trade: list, pair: MpxPair):
        maker_amount = Wad(int(trade['attributes']['maker-asset-filled-amount']))
        taker_amount = Wad(int(trade['attributes']['taker-asset-filled-amount']))

        is_sell = pair.sell_token_address == ERC20Asset.deserialize(trade['attributes']['taker-asset-data']).token_address
        price = maker_amount / taker_amount if is_sell else taker_amount / maker_amount
        amount = taker_amount if is_sell else maker_amount

        return Trade(trade_id=trade['id'],
                     timestamp=int(float(trade['attributes']['updated-at'])) // 1000,
                     pair=trade['attributes']['pair-name'],
                     is_sell=is_sell,
                     price=price,
                     amount=amount)


class MpxApi(PyexAPI):
    """mpexchange API interface.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, zrx_exchange: ZrxExchangeV2, fee_recipient: Address, timeout: float):
        assert (isinstance(api_server, str))
        assert (isinstance(zrx_exchange, ZrxExchangeV2))
        assert (isinstance(fee_recipient, Address))

        self.api_server = api_server
        self.zrx_exchange = zrx_exchange
        self.timeout = timeout
        self.fee_recipient = fee_recipient

        self.token = None

    def authenticate(self):
        data = self._http_unauthenticated("GET", f"/json_web_tokens/{self.zrx_exchange.web3.eth.defaultAccount}", {})
        nonce = data['data']['attributes']['nonce']

        signature = eth_sign(bytes(nonce, 'utf-8'), self.zrx_exchange.web3)
        data['data']['attributes']['signature'] = signature
        result = self._http_unauthenticated("PUT", f"/json_web_tokens/{self.zrx_exchange.web3.eth.defaultAccount}",
                                            data)

        self.token = result['data']['attributes']['token']

    def get_markets(self):
        return self._http_unauthenticated("GET", "/token_pairs", {})

    def get_pair(self, pair: str):
        assert (isinstance(pair, str))
        return self._http_unauthenticated("GET", f"/token_pairs?filter[pair-name]={pair}", {})

    def get_fee_recipients(self):
        return self._http_unauthenticated("GET", "/fee_recipients", {})

    def get_orders(self, pair: MpxPair) -> List[Order]:
        assert (isinstance(pair, MpxPair))

        orders = self._http_authenticated("GET", f"/orders?filter[pair-name]={pair.get_pair_name()}&filter[state]=open"
                                                 f"&filter[maker-address||sender-address]={self.zrx_exchange.web3.eth.defaultAccount}",
                                                 {})

        return list(map(lambda item: Order.from_list(item, pair), orders['data']))

    def place_order(self, pair: Pair, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert (isinstance(pair, Pair))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, Wad))
        assert (isinstance(amount, Wad))

        pay_token = pair.sell_token_address if is_sell else pair.buy_token_address
        pay_amount = amount if is_sell else amount * price

        buy_token = pair.buy_token_address if is_sell else pair.sell_token_address
        buy_amount = amount * price if is_sell else amount

        expiration = int((datetime.datetime.today() + datetime.timedelta(days=3)).strftime("%s"))

        order = self.zrx_exchange.create_order(pay_asset=ERC20Asset(pay_token),
                                               pay_amount=pay_amount,
                                               buy_asset=ERC20Asset(buy_token),
                                               buy_amount=buy_amount,
                                               expiration=expiration)

        order.fee_recipient = self.fee_recipient
        signed_order = self.zrx_exchange.sign_order(order)

        request = {
            "data": {
                "type": "orders",
                "attributes": {
                    "exchange-address": signed_order.exchange_contract_address.address.lower(),
                    "expiration-time-seconds": str(signed_order.expiration),
                    "fee-recipient-address": self.fee_recipient.address.lower(),
                    "maker-address": signed_order.maker.address.lower(),
                    "maker-asset-amount": str(signed_order.pay_amount.value),
                    "maker-asset-data": ERC20Asset(pay_token).serialize(),
                    "maker-fee": str(signed_order.maker_fee.value),
                    "salt": str(signed_order.salt),
                    "sender-address": signed_order.sender.address.lower(),
                    "taker-address": signed_order.taker.address.lower(),
                    "taker-asset-amount": str(signed_order.buy_amount.value),
                    "taker-asset-data": ERC20Asset(buy_token).serialize(),
                    "taker-fee": str(signed_order.taker_fee.value),
                    "signature": signed_order.signature
                }
            }
        }

        side = "SELL" if is_sell else "BUY"
        self.logger.info(f"Placing order ({side}, amount {amount} of {pair},"
                         f" price {price})...")

        result = self._http_authenticated("POST", "/orders", request)
        order_id = result['data']['id']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert (isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")
        self._http_authenticated("DELETE", f"/orders/{order_id}", {})

        return True

    def get_trades(self, pair: Pair, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, Pair))
        assert(page_number == 1)

        trades = self._http_unauthenticated("GET", f"/fills?filter[pair-name]={pair.get_pair_name()}"
                                                   f"&filter[maker-address||taker-address]={self.zrx_exchange.web3.eth.defaultAccount}",
                                                   {})['data']

        return list(map(lambda item: Trade.from_list(item, pair), trades))

    def get_all_trades(self, pair: Pair, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, Pair))
        assert(page_number == 1)

        trades = self._http_unauthenticated("GET", f"/fills?filter[pair-name]={pair.get_pair_name()}", {})['data']

        return list(map(lambda item: Trade.from_list(item, pair), trades))

    def _http_authenticated(self, method: str, resource: str, body: dict):
        assert (isinstance(method, str))
        assert (isinstance(resource, str))
        assert (isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             headers={
                                                 'Content-Type': 'application/vnd.api+json',
                                                 'Authorization': f'Bearer {self.token}',
                                             },
                                             timeout=self.timeout))

    def _http_unauthenticated(self, method: str, resource: str, body: dict):
        assert (isinstance(method, str))
        assert (isinstance(resource, str))
        assert (isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    def _result(self, result) -> Optional[dict]:
        if result.status_code == 204:
            return {}

        if not result.ok:
            raise Exception(f"MPExchange API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"MPExchange API invalid JSON response: {http_response_summary(result)}")

        return data
