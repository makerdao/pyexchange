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
from pyexchange.api import PyexAPI
import hmac
import hashlib
import time
import requests
import json

from urllib.parse import urlencode

from pyflex import Address, Wad
from pyflex.util import http_response_summary
from pyexchange.model import Order, Trade
from typing import Optional, List


class BinanceUsOrder(Order):
    @staticmethod
    def create(item):
        return BinanceUsOrder(order_id=str(item['orderId']),
                     pair=item['symbol'],
                     is_sell=True if item['side'] == 'SELL' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['origQty']),
                     timestamp=item['time'])


class BinanceUsTrade(Trade):
    @staticmethod
    def from_my_trade(pair, trade):
        return BinanceUsTrade(trade_id=str(trade['id']),
                     timestamp=trade['time'],
                     pair=pair,
                     is_sell=not trade['isBuyer'],
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['qty']))
    

    @staticmethod
    def from_trade(pair, trade):
        return BinanceUsTrade(trade_id=str(trade['id']),
                     timestamp=trade['time'],
                     pair=pair,
                     is_sell=not trade['isBuyerMaker'],
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['qty']))


class BinanceUsApi(PyexAPI):
    """Binance US API interface.

    Implemented based on https://github.com/binance-us/binance-official-api-docs/blob/master/rest-api.md
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout

    def get_precision(self, pair):
        assert(isinstance(pair, str))
        symbols = self._http_authenticated("GET", "/api/v3/exchangeInfo", {})['symbols']
        pair = self._fix_pair(pair)

        for symbol_data in symbols:
            if pair == symbol_data['symbol']:
                return symbol_data['quoteAssetPrecision'], symbol_data['quotePrecision']
        else:
            raise ValueError(f'Not supported pair {pair} on Binance US.')

    def get_balances(self):
        balances = self._http_authenticated("GET", f"/api/v3/account", {})['balances']

        return {
            balance['asset']: { "free": balance["free"], "locked": balance["locked"] }
            for balance in balances
        }

    def get_balance(self, coin: str):
        assert(isinstance(coin, str))
        for balance in self.get_balances():
            if balance['asset'] == coin:
                return balance

    def get_orders(self, pair: str) -> List[BinanceUsOrder]:
        assert(isinstance(pair, str))
        pair = self._fix_pair(pair)

        orders = self._http_authenticated("GET", f"/api/v3/openOrders", {'symbol': pair})

        return list(map(lambda order: BinanceUsOrder.create(order), orders))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        pair = self._fix_pair(pair)
        
        data = {
            'symbol': pair,
            'side': "SELL" if is_sell else "BUY",
            'type': 'LIMIT', 
            'quantity': float(amount),
            'price': float(price),
            'timeInForce': 'GTC'
        }

        self.logger.info(f"Placing order (Good Till Cancel, {data['side']}, amount {data['quantity']} of {pair},"
                         f" price {data['price']})...")
                         
        result = self._http_authenticated("POST", "/api/v3/order", data)
        order_id =  result['orderId']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return str(order_id)

    def cancel_order(self, order_id: str, pair: str) -> bool:
        assert(isinstance(order_id, str))
        assert(isinstance(pair, str))

        self.logger.info(f"Cancelling order #{order_id} on pair {pair}...")

        result = self._http_authenticated("DELETE", "/api/v3/order", {'orderId': order_id, 'pair': pair})

        return ('status' in result) and (result['status'] == "CANCELED")
    
    def get_trades(self, pair: str, page_number: int = 1) -> List[BinanceUsTrade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)
        
        trades_result = self._http_authenticated("GET", "/api/v3/myTrades", {'symbol': self._fix_pair(pair)})

        return list(map(lambda trade: BinanceUsTrade.from_my_trade(pair, trade), trades_result))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[BinanceUsTrade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        
        trades_result = self._http_unauthenticated("GET", "/api/v3/trades", {'symbol': self._fix_pair(pair)})

        return list(map(lambda trade: BinanceUsTrade.from_trade(pair, trade), trades_result))

    def _http_unauthenticated(self, method: str, resource: str, params: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             params=params,
                                             timeout=self.timeout))

    def _http_authenticated(self, method: str, resource: str, params: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(params, dict) or (params is None))

        timestamp = int(round(time.time() * 1000)) 
        data = {**params, **{'timestamp': timestamp}}  

        message = urlencode(data)
        message = message.encode('ascii')
        hmac_key = self.secret_key.encode('ascii')
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_hex = signature.digest().hex()

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             params={**data, **{'signature': signature_hex}},
                                             headers={
                                                 'X-MBX-APIKEY': self.api_key,
                                             },
                                             timeout=self.timeout))

    @staticmethod
    def _fix_pair(pair) -> str:
        return str.join('', pair.split('-'))

    @staticmethod
    def _result(result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Binnance API response: {http_response_summary(result)}")

        logging.debug(f"Received: {result.text}")
        try:
            data = result.json()
        except json.JSONDecodeError:
            raise ValueError(f"Binnance API invalid JSON response: {http_response_summary(result)}")
        return data
