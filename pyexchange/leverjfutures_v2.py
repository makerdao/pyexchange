# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2021 mitakash
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
from pyexchange.api import PyexAPI
import dateutil.parser
import time
import requests
import json
from leverj_ordersigner import futures
from pprint import pformat
from pymaker import Contract, Address, Transact, Wad
from pymaker.util import http_response_summary, bytes_to_hexstring
from typing import Optional
from pymaker.sign import eth_sign, to_vrs
from web3 import Web3
from typing import Optional, List
import urllib.request
from decimal import *

_context = Context(prec=1000, rounding=ROUND_DOWN)


class Order:
    def __init__(self,
                 order_id: str,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(order_id, str))
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

    @staticmethod
    def from_list(item: list, pair: str):
        return Order(order_id=item['uuid'],
                     pair=pair,
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['quantity']))


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int) or (trade_id is None) or isinstance(trade_id, str))
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
    def from_our_list(pair, trade):
        return Trade(trade_id=trade['executionId'],
                     timestamp=int(int(trade['eventTime'])/1000000),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['quantity']))

    @staticmethod
    def from_all_list(pair, trade):
        return Trade(trade_id=None,
                     timestamp=int(trade['date']),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['volume']))


class LeverjFuturesAPI(PyexAPI):
    """LeverJ Futures API interface.
    """

    logger = logging.getLogger()
    MAX_INDEX_VARIANCE = 0.0085

    def __init__(self, web3: Web3, api_server: str, account_id: str, api_key: str, api_secret: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(api_secret, str))
        assert(isinstance(account_id, str))

        url = api_server + "/futures/api/v1/all/config"
        self.web3 = web3

        self.api_server = api_server
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.timeout = timeout
        self.config = requests.get(url).json()


    def get_account(self):
        return self._http_authenticated("GET", "/futures/api/v1", "/account", None)

    def get_balances(self):
        return self._http_authenticated("GET", "/futures/api/v1", "/account/balance", None)

    def get_balance(self, coin: str):
        assert(isinstance(coin, str))
        balances = self.get_balances()
        for key in balances:
            if balances[key]['symbol'] == coin:
                return balances[key]['plasma']

    def get_available_balance(self, coin: str):
        assert(isinstance(coin, str))
        balances = self.get_balances()
        for key in balances:
            if balances[key]['symbol'] == coin:
                return balances[key]['available']

    def get_quote_balance(self, quote_asset_address: str) -> str:
        assert(isinstance(quote_asset_address, str))
        balances = self.get_balances()
        quote_balance = balances[quote_asset_address]['available']
        return quote_balance

    def get_plasma_balance(self, quote_asset_address: str) -> str:
        assert(isinstance(quote_asset_address, str))
        balances = self.get_balances()
        quote_balance = balances[quote_asset_address]['plasma']
        return quote_balance

    def get_pending(self, coin: str):
        assert(isinstance(coin, str))
        balances = self.get_balances()
        for key in balances:
            if balances[key]['symbol'] == coin:
                return balances[key]['pending']

    def get_positions(self):
        return self._http_authenticated("GET", "/futures/api/v1", "/account/position", None)

    def get_position(self, coin: str):
        assert(isinstance(coin, str))
        positions = self.get_positions()
        for index, position in enumerate(positions):
            if position['instrument'] == self._get_instrument_id_by_asset_name(coin.upper()):
                return position['size']

    def get_position_in_wad(self, coin: str) -> Wad:
        assert(isinstance(coin, str))
        position = self.get_position(coin)
        if (coin == 'BTC'):
            decimals = Decimal(10)**Decimal(18)
        elif (coin == 'ETH'):
            decimals = Decimal(10)**Decimal(18)
        else:
            raise ValueError(f'{coin} not supported')
        position = position or 0
        position_in_wad = Wad(int((Decimal(position)*decimals).quantize(1, context=_context)))
        return position_in_wad

    def _get_instrument_id_by_asset_name(self, name: str):
        asset_name_to_instrument_id_map = {'BTC': '1', 'ETH': '2'}
        return asset_name_to_instrument_id_map[name]

    def get_config(self):
        return self.config

    def get_futures_exchange_id(self):
        config = self.get_config()
        return config['config']['network']['id']

    def get_custodian_address(self):
        config = self.get_config()
        return config['config']['network']['gluon']

    def get_product(self, pair: str):
        assert(isinstance(pair, str))
        return self.get_config()['instruments'][pair]

    def get_tickSize(self, pair: str):
        assert(isinstance(pair, str))
        return self.get_product(pair)["tickSize"]

    def get_minimum_order_quantity(self, pair: str):
        #Reads the instrument configuration to get the smallest possible order quantity for the given instrument.
        #The base significant digit value decides the smallest possible order quantity.
        assert(isinstance(pair, str))
        orderInstrument = self.get_product(pair)
        base_significant_digits = orderInstrument['baseSignificantDigits']
        return Decimal(1)/(Decimal(pow(Decimal(10), Decimal(base_significant_digits))))

    def get_info(self):
        return self._http_authenticated("GET", "/futures/api/v1", "/all/info", None)

    def get_all_orders(self):
        return self._http_authenticated("GET", "/futures/api/v1", "/order", None)

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))
        result_pair =  []
        result = self._http_authenticated("GET", "/futures/api/v1", "/order", None)
        for item in result:
            if item['instrument'] == pair:
                result_pair.append(item)
        return list(map(lambda item: Order.from_list(item, pair), result_pair))

    def get_id_from_pair(self, pair: str) -> str:
        assert(isinstance(pair, str))
        if pair=="BTCUSD":
            return "1"
        elif pair=="ETHUSD":
            return "2"
        else:
            self.logger.info(f'You have passed in an unsupported pair')

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        count = 200
        result_pair =  []
        result = self._http_authenticated("GET", "/futures/api/v1", f"/account/execution?count={count}", None)
        for item in result:
            if item['instrument'] == self.get_id_from_pair(pair):
                result_pair.append(item)

        return list(map(lambda item: Trade.from_our_list(pair, item), result_pair))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        result = self._http_authenticated("GET", "/futures/api/v1", f"/instrument/{self.get_id_from_pair(pair)}/trade", None)

        return list(map(lambda item: Trade.from_all_list(pair, item), result))

    def get_orderbook_symbol(self, symbol: str):
        return self._http_authenticated("GET", "/futures/api/v1", f"/instrument/{symbol}/orderbook", None)

    def round_with_precision(self, value, precision):
        val = round(float(value), precision)
        if precision == 0:
            return int(val)
        else:
            return val
    
    def get_margin_per_fraction(self, orderInstrument, price, leverage):
        estimated_entry_price = price
        max_leverage = orderInstrument['maxLeverage']
        if leverage > max_leverage:
            self.logger.info(f'You have specified a leverage of {leverage} but the max leverage allowed on this instrument is {max_leverage}.')
        base_significant_digits = orderInstrument['baseSignificantDigits']
        decimals = orderInstrument['quote']['decimals']
        multiplier = Decimal(
            pow(Decimal(10), Decimal(decimals - base_significant_digits)))
        intermediate_value = Decimal((Decimal(estimated_entry_price) * multiplier) / Decimal(leverage)).to_integral_exact()
        return int(Decimal(intermediate_value) * Decimal(pow(Decimal(10), Decimal(base_significant_digits))))

    def createNewOrder(self, side: str, price: str, triggerPrice: str, quantity: str, orderInstrument: dict, orderType: str, leverage: float = 1.0, reduceOnly: bool = False) -> dict:
        price_precision = orderInstrument.get('quoteSignificantDigits')
        quantity_precision = orderInstrument.get('baseSignificantDigits')
        # default leverage is set to 1.0 which means you aren't using any leverage. If you want 5K DAI position to control 10K DAI worth of BTC, use leverage of 2
        order = {
                'accountId': self.account_id,
                'originator': self.api_key,
                'instrument': orderInstrument['id'],
                'price': self.round_with_precision(price, price_precision),
                'quantity': self.round_with_precision(quantity, quantity_precision),
                'marginPerFraction': str(self.get_margin_per_fraction(orderInstrument, price, leverage)),
                'side': side,
                'orderType': orderType,
                'timestamp': int(time.time()*1000000),
                'quote': orderInstrument['quote']['address'],
                'isPostOnly': False,
                'reduceOnly': reduceOnly,
                'clientOrderId': 1,
                'triggerPrice': self.round_with_precision(triggerPrice, price_precision),
                'indexSanity': self.MAX_INDEX_VARIANCE
                }
        order['signature'] = futures.sign_order(order, orderInstrument, self.api_secret)
        self.logger.info(f'order: {order}')
        return order

    def place_order(self, pair: str, triggerPrice: str, orderType: str, is_sell: bool, price: Wad, amount: Wad, leverage: Wad, reduceOnly: bool):
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        orderInstrument = self.get_product(pair)
        side = "sell" if is_sell else "buy"
        price = str(price)
        triggerPrice = str(triggerPrice)
        quantity = str(amount)
        order = self.createNewOrder(side, price, triggerPrice, quantity, orderInstrument, orderType, float(leverage), reduceOnly)
        order_quantity = order['quantity']
        if order_quantity > 0:
            self.logger.info(f'order_quantity: {order_quantity}')
            self.logger.info(f'LEVERJ: order is {order}')
            return self._http_authenticated("POST", "/futures/api/v1", "/order", [order])[0]['uuid']

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))
        self.logger.info(f'cancelled order: {order_id}')

        result = self._http_authenticated("DELETE", "/futures/api/v1", f"/order/{order_id}", None)

        if order_id != result[0][0]:
            return False

        return True

    def cancel_all_orders(self) -> List:
        result = []

        orders = self.get_all_orders()

        for order in orders:
            order_id = order['uuid']
            result.append(self.cancel_order(order_id))

        return result

    def _http_authenticated(self, method: str, api_path: str, resource: str, body):
        assert(isinstance(method, str))
        assert(isinstance(api_path, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None) or (body, list))

        data = json.dumps(body, separators=(',', ':'))
        nonce = int(time.time()*1000)

        params = {
            'method': method,
            'uri': resource,
            'nonce': nonce
            }


        if body is not None:
            params['body'] = body

        payload = str(nonce)
        signature = self._create_signature(payload)

        v, r, s = to_vrs(signature)

        auth_header = f"NONCE {self.account_id}.{self.api_key}"\
            f".{v}"\
            f".{bytes_to_hexstring(r)}"\
            f".{bytes_to_hexstring(s)}"

        headers={ "Authorization": auth_header, "Nonce": str(nonce) }
        if body is not None:
            headers["Content-Type"] = "application/json"

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{api_path}{resource}",
                                             data=data,
                                             headers=headers,
                                             timeout=self.timeout))

    def _create_signature(self, params: str) -> str:
        assert(isinstance(params, str))

        return eth_sign(bytes(params, 'utf-8'), self.web3, self.api_secret, False, Address(self.account_id))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Leverj API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise ValueError(f"Leverj API invalid JSON response: {http_response_summary(result)}")

        return data

