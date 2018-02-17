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

import datetime
import logging
import time
from pprint import pformat
from typing import Optional, List

import dateutil.parser
import pytz
import requests

import pymaker.zrx
from pyexchange.util import sort_trades, filter_trades
from pymaker import Wad
from pymaker.sign import eth_sign
from pymaker.zrx import ZrxExchange


class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_remaining: Wad):

        assert(isinstance(order_id, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_remaining, Wad))

        self.order_id = order_id
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.amount_remaining = amount_remaining

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount_remaining if self.is_sell else self.amount_remaining*self.price

    def __repr__(self):
        return pformat(vars(self))


class Trade:
    def __init__(self,
                 trade_id: id,
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 amount_symbol: str,
                 money: Wad,
                 money_symbol: str,
                 base_fee: Wad,
                 trading_fee: Wad):
        assert(isinstance(trade_id, int))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(amount_symbol, str))
        assert(isinstance(money, Wad))
        assert(isinstance(money_symbol, str))
        assert(isinstance(base_fee, Wad))
        assert(isinstance(trading_fee, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.amount_symbol = amount_symbol
        self.money = money
        self.money_symbol = money_symbol
        self.base_fee = base_fee
        self.trading_fee = trading_fee

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
               self.base_fee == other.base_fee and \
               self.trading_fee == other.trading_fee

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
                     self.base_fee,
                     self.trading_fee))

    def __repr__(self):
        return pformat(vars(self))


class ParadexApi:
    """Paradex API interface.

    Developed according to the following manual:
    <https://github.com/ParadexRelayer/Consumer-API-docs>.
    """

    logger = logging.getLogger()

    def __init__(self, zrx_exchange: ZrxExchange, api_server: str, api_key: str, timeout: float):
        assert(isinstance(zrx_exchange, ZrxExchange) or (zrx_exchange is None))
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(timeout, float))

        self.zrx_exchange = zrx_exchange
        self.api_server = api_server
        self.api_key = api_key
        self.timeout = timeout
        self.nonce = 0

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get("/v0/ticker", f"market={pair}")

    def get_balances(self):
        return self._http_post("/v0/balances", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders_open = self._http_post("/v0/orders", {
            'market': pair,
            'state': 'open'
        })

        orders_unfunded = self._http_post("/v0/orders", {
            'market': pair,
            'state': 'unfunded'
        })

        return list(map(lambda item: Order(order_id=int(item['id']),
                                           pair=pair,
                                           is_sell=item['type'] == 'sell',
                                           price=Wad.from_number(item['price']),
                                           amount=Wad.from_number(item['amount']),
                                           amount_remaining=Wad.from_number(item['amountRemaining'])),
                        list(orders_open) + list(orders_unfunded)))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad, expiry: int) -> int:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(expiry, int))

        # `zrx_exchange` has to be present if we want to place orders
        assert(self.zrx_exchange is not None)

        self.logger.info(f"Placing order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price})...")

        order_params = self._http_post("/v0/orderParams", {
            'market': pair,
            'orderType': 'sell' if is_sell else 'buy',
            'price': str(price),
            'amount': str(amount),
            'expirationDate': datetime.datetime.fromtimestamp(time.time() + expiry, pytz.UTC).strftime("%Y-%m-%d %H:%M:%S.000000%z")
        })

        order = pymaker.zrx.Order.from_json(self.zrx_exchange, order_params['zrxOrder'])
        order = self.zrx_exchange.sign_order(order)
        fee = self._calculate_fee(is_sell, price, amount, order)

        result = self._http_post("/v0/order", {
            'exchangeContractAddress': str(order.exchange_contract_address.address),
            'expirationUnixTimestampSec': str(order.expiration),
            'feeRecipient': str(order.fee_recipient.address),
            'maker': str(order.maker.address),
            'makerFee': str(order.maker_fee.value),
            'makerTokenAddress': str(order.pay_token.address),
            'makerTokenAmount': str(order.pay_amount.value),
            'salt': str(order.salt),
            'taker': str(order.taker.address),
            'takerFee': str(order.taker_fee.value),
            'takerTokenAddress': str(order.buy_token.address),
            'takerTokenAmount': str(order.buy_amount.value),
            'v': str(order.ec_signature_v),
            'r': str(order.ec_signature_r),
            's': str(order.ec_signature_s),
            'feeId': order_params['fee']['id']
        })
        order_id = result['id']

        self.logger.info(f"Placed order ({'SELL' if is_sell else 'BUY'}, amount {amount} of {pair},"
                         f" price {price}, fee {float(fee)*100:.4f}%) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: int) -> bool:
        assert(isinstance(order_id, int))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_post("/v0/orderCancel", {
            'id': order_id
        })
        success = result['status']

        if success:
            self.logger.info(f"Cancelled order #{order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order_id}")

        return success

    def get_trades(self, pair: str, **kwargs) -> List[Trade]:
        assert(isinstance(pair, str))

        result = self._http_post("/v0/trades", {
            'market': pair
        })

        result = filter(lambda item: item['completedAt'] is not None, result)
        trades = list(map(lambda item: Trade(trade_id=int(item['id']),
                                             timestamp=int(dateutil.parser.parse(item['completedAt']).timestamp()),
                                             pair=pair,
                                             is_sell=item['type'] == 'sell',
                                             price=Wad.from_number(item['price']),
                                             amount=Wad.from_number(item['amount']),
                                             amount_symbol=item['baseToken'],
                                             money=Wad.from_number(item['amount'])*Wad.from_number(item['price']),
                                             money_symbol=item['quoteToken'],
                                             base_fee=Wad.from_number(item['baseFee']),
                                             trading_fee=Wad.from_number(item['tradingFee'])), result))

        trades = sort_trades(trades)
        trades = filter_trades(trades, **kwargs)

        return trades

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Paradex API invalid HTTP response: {result.status_code} {result.reason}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Paradex API invalid JSON response: {result.text}")

        if 'error' in data:
            if 'code' in data['error'] and data['error']['code'] == 107:
                new_nonce = data['error']['currentNonce'] + 1
                self.logger.info(f"Invalid nonce, tried {self.nonce - 1} but instructed to change to {new_nonce}")
                self.nonce = new_nonce

                return None

            raise Exception(f"Negative Paradex response: {data}")

        return data

    @staticmethod
    def _calculate_fee(is_sell: bool, price: Wad, amount: Wad, zrx_order: pymaker.zrx.Order) -> Wad:
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(zrx_order, pymaker.zrx.Order))

        if is_sell:
            expected_buy_amount = amount*price
        else:
            expected_buy_amount = amount

        return (expected_buy_amount - zrx_order.buy_amount) / expected_buy_amount

    def _create_signature(self, params: dict) -> str:
        assert(isinstance(params, dict))

        try:
            from sha3 import keccak_256
        except ImportError:
            from sha3 import sha3_256 as keccak_256

        keys = ''
        values = ''
        for key in sorted(params.keys()):
            keys += key
            values += str(params[key])

        message = bytes(keys + values, 'utf-8')
        return eth_sign(message, self.zrx_exchange.web3)

    def _create_sig_header(self, params: dict):
        assert(isinstance(params, dict))

        signature = self._create_signature(params)
        if signature.endswith("1c"):
            return (signature[0:130] + "01")[2:]
        elif signature.endswith("1b"):
            return (signature[0:130] + "00")[2:]
        else:
            raise Exception(f"Invalid signature: {signature}")

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         headers={"API-KEY": self.api_key},
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        max_attempts = 3
        for attempt in range(0, max_attempts):
            params_with_nonce = params.copy()
            params_with_nonce['nonce'] = self.nonce
            self.nonce += 1

            result = self._result(requests.post(url=f"{self.api_server}{resource}",
                                                json=params_with_nonce,
                                                headers={
                                                    "API-KEY": self.api_key,
                                                    "API-SIG": self._create_sig_header(params_with_nonce)
                                                },
                                                timeout=self.timeout))

            # result will be `None` if we need to readjust nonce
            # in this case we will try again in the next iteration
            if result is not None:
                return result

        raise Exception(f"Couldn't get a response despite {max_attempts} attempts to readjust the nonce")
