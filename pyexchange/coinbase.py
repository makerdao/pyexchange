# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 grandizzy
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
import hmac
import hashlib
import time
import base64
import requests
import json

import dateutil.parser

from pyflex import Address, Wad
from pyflex.util import http_response_summary
from typing import Optional, List


class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

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
        return Order(order_id=item['id'],
                     pair=item['product_id'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['size']))


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int) or (trade_id is None))
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
        return Trade(trade_id=trade['trade_id'],
                     timestamp=int(dateutil.parser.parse(trade['created_at']).timestamp()),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['size']))

    @staticmethod
    def from_all_list(pair, trade):
        return Trade(trade_id=trade['trade_id'],
                     timestamp=int(dateutil.parser.parse(trade['time']).timestamp()),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['size']))


class CoinbaseApi(PyexAPI):
    """Coinbase API interface.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, password: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(password, str))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.password = password
        self.timeout = timeout

    def get_balances(self):
        return self._http_authenticated("GET", "/accounts", {})

    def get_balance(self, coin: str):
        assert(isinstance(coin, str))
        for balance in self.get_balances():
            if balance['currency'] == coin:
                return balance

    def get_product(self, pair: str):
        return self._http_unauthenticated("GET", f"/products/{pair}", {})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        orders = self._http_authenticated("GET", f"/orders?product_id={pair}", {})

        return list(map(lambda item: Order.from_list(item, pair), orders))

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        data = {
            "size": str(amount),
            "price": str(price),
            "side": "sell" if is_sell else "buy",
            "product_id": pair
        }

        self.logger.info(f"Placing order ({data['side']}, amount {data['size']} of {pair},"
                         f" price {data['price']})...")

        result = self._http_authenticated("POST", "/orders", data)
        order_id = result['id']

        self.logger.info(f"Placed order (#{result}) as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        result = self._http_authenticated("DELETE", f"/orders/{order_id}", {})

        if order_id not in result:
            return False

        return True

    def cancel_all_orders(self) -> List:
        self.logger.info(f"Cancelling all orders ...")

        result = self._http_authenticated("DELETE", "/orders", {})
        success = len(result) > 0

        if success:
            self.logger.info(f"Cancelled orders : #{result}")
        else:
            self.logger.info(f"No order canceled ")

        return result

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_authenticated("GET", f"/fills?product_id={pair}", {})

        return list(map(lambda item: Trade.from_our_list(pair, item), result))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        limit = 100

        result = self._http_unauthenticated("GET", f"/products/{pair}/trades?before={page_number}&limit={limit}", {})

        return list(map(lambda item: Trade.from_all_list(pair, item), result))

    def get_profiles(self):
        # Returns list of profiles; one profile exists for each portfolio/account/subaccount
        return self._http_authenticated("GET", "/profiles", {})

    def get_profile(self, portfolio: str):
        # Retrieves the profile identifier for a particular account or subaccount based on portfolio name
        assert isinstance(portfolio, str)

        matching = list(filter(lambda p: p['name'] == portfolio, self.get_profiles()))
        if len(matching) > 1:
            raise ValueError("Multiple profiles match that portfolio name; please adjust names via Coinbase Pro GUI")
        elif len(matching) < 1:
            raise ValueError(f"No profile was found for portfolio {portfolio}")
        else:
            return matching[0]['id']

    def transfer(self, amount: Wad, coin: str, from_portfolio: str, to_portfolio: str):
        # Moves funds from between default account and subaccount;
        # must be executed using the API key associated with the sender account
        assert isinstance(amount, Wad)
        assert isinstance(coin, str)
        assert isinstance(from_portfolio, str)
        assert isinstance(to_portfolio, str)

        profile_from = self.get_profile(from_portfolio)
        profile_to = self.get_profile(to_portfolio)

        data = {
            "from": profile_from,
            "to": profile_to,
            "currency": coin,
            "amount": str(float(amount))
        }

        self.logger.info(f"Transferring {data['amount']} {coin} from {from_portfolio} ({profile_from}) "
                         f"to {to_portfolio} ({profile_to})")

        return self._http_authenticated("POST", "/profiles/transfer", data)

    def get_coinbase_wallets(self):
        return self._http_authenticated("GET", "/coinbase-accounts", {})

    def get_coinbase_wallet(self, coin: str):
        assert isinstance(coin, str)
        coinbase_wallets = self.get_coinbase_wallets()
        for wallet in coinbase_wallets:
            if wallet['currency'] == coin:
                return wallet
        return None

    def get_coinbase_wallet_address(self, coin: str) -> Address:
        assert isinstance(coin, str)
        wallet = self.get_coinbase_wallet(coin)
        if wallet is None:
            raise ValueError(f"Wallet for {coin} not found; ensure Coinbase Pro supports this token")
        wallet_id = wallet['id']
        result = self._http_authenticated("POST", f"/coinbase-accounts/{wallet_id}/addresses", {})
        return Address(result['address'])

    def withdraw(self, amount: Wad, coin: str, address: Address) -> str:
        assert isinstance(amount, Wad)
        assert isinstance(coin, str)
        assert isinstance(address, Address)

        data = {
            "amount": str(float(amount)),
            "currency": coin,
            "crypto_address": address.address
        }
        self.logger.info(f"Withdrawing {amount} {coin} to {address.address}")
        result = self._http_authenticated("POST", "/withdrawals/crypto", data)

        withdrawal_id = result['id']
        self.logger.info(f"Submitted withdrawal {withdrawal_id}")
        return withdrawal_id

    def _http_authenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        timestamp = str(time.time())
        message = ''.join([timestamp, method, resource, data or ''])
        message = message.encode('ascii')
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             headers={
                                                 'Content-Type': 'Application/JSON',
                                                 'CB-ACCESS-SIGN': signature_b64,
                                                 'CB-ACCESS-TIMESTAMP': timestamp,
                                                 'CB-ACCESS-KEY': self.api_key,
                                                 'CB-ACCESS-PASSPHRASE': self.password
                                             },
                                             timeout=self.timeout))

    def _http_unauthenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    @staticmethod
    def _result(result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Coinbase API response: {http_response_summary(result)}")

        if result.content and result.content != b'OK':
            logging.debug(f"Received: {result.content}")
            try:
                data = result.json()
            except json.JSONDecodeError:
                raise ValueError(f"Coinbase API invalid JSON response: {http_response_summary(result)}")
            return data
