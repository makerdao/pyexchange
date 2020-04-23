# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 EdNoepel
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

import json
import jwt
import logging
import requests
import simplefix
import time
import uuid

from typing import List

from pyexchange.api import PyexAPI
from pyexchange.fix import FixEngine
from pyexchange.model import Order, Trade
from pymaker.util import http_response_summary
from pymaker.numeric import Wad


class ErisxOrder(Order):

    @staticmethod
    def from_message(item):
        return Order(order_id=item['oid'],
                     timestamp=item['created_at'],
                     book=item['book'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['amount']))

class ErisxApi(PyexAPI):
    """
    Implementation logic for interacting with the ErisX exchange, which uses FIX for order management and
    market data, and a WebAPI for retrieving account balances.

    ErisX documentation available here: https://www.erisx.com/wp-content/uploads/2020/03/ErisX-FIX-4.4-Spec-V3.3.pdf
    """


    logger = logging.getLogger()
    timeout = 5

    def __init__(self, fix_trading_endpoint: str, fix_trading_user: str,
                 fix_marketdata_endpoint: str, fix_marketdata_user: str, password: str,
                 clearing_url: str, api_key: str, api_secret: str):
        assert isinstance(fix_trading_endpoint, str)
        assert isinstance(fix_trading_user, str)
        assert isinstance(fix_marketdata_endpoint, str)
        assert isinstance(fix_marketdata_user, str)
        assert isinstance(password, str)

        assert isinstance(clearing_url, str)
        assert isinstance(api_key, str)
        assert isinstance(api_secret, str)

        self.fix_trading = ErisxFix(fix_trading_endpoint, fix_trading_user, fix_trading_user, password)
        self.fix_trading.logon()
        self.fix_trading_user = fix_marketdata_user

        self.fix_marketdata = ErisxFix(fix_marketdata_endpoint, fix_marketdata_user, fix_trading_user, password)
        self.fix_marketdata.logon()
        self.fix_marketdata_user = fix_marketdata_user

        self.clearing_url = clearing_url
        self.api_secret = api_secret
        self.api_key = api_key

    def __del__(self):
        self.fix_marketdata.logout()
        self.fix_trading.logout()

    def ticker(self, pair):
        # TODO: Subscribe to L1 data, await receipt, and then unsubscribe and return the data.
        raise NotImplementedError()

    def get_markets(self):
        # Send 35=x, await 35=y
        message = self.fix_marketdata.create_message('x')
        message.append_pair(320, 0)
        message.append_pair(559, 0)
        message.append_pair(55, 'NA')
        message.append_pair(460, 2)
        self.fix_marketdata.write(message)
        message = self.fix_marketdata.wait_for_response('y')
        return ErisxFix.parse_security_list(message)

    # filter out the response from get markets
    def get_pair(self, pair):
        return self.get_markets()[pair]

    # def get_balances(self):
    #     # Call into the /accounts method of ErisX Clearing WebAPI, which provides a balance of each coin.
    #     # They also offer a detailed /balances API, which I don't believe we need at this time.
    #     response = self._http_post("accounts", {})
    #     if "accounts" in response:
    #         return response["accounts"]
    #     else:
    #         raise RuntimeError("Couldn't interpret response")

    def get_balances(self):
        response = self._http_post("balances", {"account_id": "637abe14-6fe2-495f-9ddb-277610a2ef26"})
        if "balances" in response:
            return response["balances"]
        else:
            raise RuntimeError("Couldn't interpret response")

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        message = self.fix_trading.create_message('AF')
        message.append_pair(584, uuid.uuid4())
        message.append_pair(585, 8)

        message.append_pair(1, self.fix_trading_user)
        self.fix_trading.write(message)
        unfiltered_orders = self.fix_trading.wait_for_orders_response()

        return list(map(lambda item: ErisxOrder.from_message(item), ErisxFix.parse_orders_list(unfiltered_orders)))

    def place_order(self, pair: str, is_sell: bool, price: float, amount: float) -> dict:
        assert(isinstance(pair, str))
        message = self.fix_trading.create_message('D')

        client_order_id = uuid.uuid4()
        side = 1 if is_sell is False else 2
        base_currency = pair.split('/')[0]

        message.append_pair(11, client_order_id)
        message.append_pair(21, 1)
        message.append_pair(15, base_currency)
        message.append_pair(54, side)
        message.append_pair(55, pair)
        message.append_pair(460, 2)
        message.append_utc_timestamp(60)
        message.append_pair(38, amount)
        message.append_pair(40, 2)  # always place limit orders
        message.append_pair(44, price)
        message.append_pair(59, 1)

        #  Optional
        message.append_pair(448, self.fix_trading_user)

        self.fix_trading.write(message)
        new_order = self.fix_trading.wait_for_response('8')

        order_id = {
            'erisx': new_order.get(37).decode('utf-8'),
            'client': new_order.get(41).decode('utf-8')
        }
        return order_id

    def cancel_order(self, order_id: dict, symbol: str, is_sell: bool):
        assert(isinstance(order_id, dict))

        side = 1 if is_sell is False else 2

        message = self.fix_trading.create_message('F')

        message.append_pair(11, uuid.uuid4())
        message.append_pair(37, order_id['erisx'])  # ErisX assigned order id
        message.append_pair(41, order_id['client'])  # Client assigned order id
        message.append_pair(55, symbol)
        message.append_pair(54, side)
        message.append_utc_timestamp(60)

        self.fix_trading.write(message)
        return self.fix_trading.wait_for_response('8')

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))

        message = self.fix_trading.create_message('AF')
        message.append_pair(584, uuid.uuid4())
        message.append_pair(585, 8)
        # message.append_pair(1, self.fix_trading_user)

        self.fix_trading.write(message)
        unfiltered_trades = self.fix_trading.wait_for_orders_response()

        return list(map(lambda item: Trade.from_message(item), ErisxFix.parse_trades_list(unfiltered_trades)))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        raise NotImplementedError()

    def _http_get(self, resource: str, params=""):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        if params:
            request = f"{resource}?{params}"
        else:
            request = resource

        return self._result(
            requests.get(url=f"{self.clearing_url}{request}",
                         headers=self._create_http_headers("GET", request, ""),
                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))
        # Auth headers are required for all requests
        return self._result(
            requests.post(url=f"{self.clearing_url}{resource}",
                          data=params,
                          headers=self._create_http_headers("POST", resource),
                          timeout=self.timeout))

    def _create_http_headers(self, method, request_path):
        assert(method in ["GET", "POST"])
        assert(isinstance(request_path, str))

        unix_timestamp = int(round(time.time()))
        payload_dict = {'sub': self.api_key, 'iat': unix_timestamp}
        token = jwt.encode(payload_dict, self.api_secret, algorithm='HS256').decode('utf-8')

        headers = {
            "Authorization": f"Bearer {token}"
        }
        return headers

    @staticmethod
    def _result(response) -> dict:
        """Interprets the response to an HTTP GET or POST request"""
        if not response.ok:
            raise Exception(f"Error in HTTP response: {http_response_summary(response)}")
        else:
            return response.json()


class ErisxFix(FixEngine):
    def __init__(self, endpoint: str, sender_comp_id: str, username: str, password: str):
        super(ErisxFix, self).__init__(endpoint=endpoint, sender_comp_id=sender_comp_id, target_comp_id="ERISX",
                                       username=username, password=password,
                                       fix_version="FIX.4.4", heartbeat_interval=10)

    @staticmethod
    def parse_security_list(m: simplefix.FixMessage) -> dict:
        security_count = int(m.get(146))
        securities = {}
        for i in range(1, security_count):

            # Required fields
            symbol = m.get(55, i).decode('utf-8')
            securities[symbol] = {
                "Product": m.get(460, i).decode('utf-8'),
                "MinPriceIncrement": float(m.get(969, i).decode('utf-8')),
                "SecurityDesc": m.get(107, i).decode('utf-8'),
                "Currency": m.get(15, i).decode('utf-8')
            }

            # Optional fields
            min_trade_vol = m.get(562, i)
            if min_trade_vol:
                securities[symbol]["MinTradeVol"] = float(min_trade_vol.decode('utf-8'))
            max_trade_vol = m.get(1140, i)
            if max_trade_vol:
                securities[symbol]["MaxTradeVol"] = float(max_trade_vol.decode('utf-8'))
            round_lot = m.get(561, i)
            if round_lot:
                securities[symbol]["RoundLot"] = float(round_lot.decode('utf-8'))

        return securities

    @staticmethod
    def parse_orders_list(messages: List[simplefix.FixMessage]) -> List:
        orders = []

        for message in messages:

            order_quantity = message.get(38).decode('utf-8')
            amount_left = message.get(151).decode('utf-8')

            logging.debug(f"amount left: {amount_left}")
            if amount_left is not 0:

                # TODO: account for tag 15, currency the order is denominated in
                # TODO: account for partial order fills
                side = 'buy' if message.get(54).decode('utf-8') == 1 else 'sell'
                oid = message.get(37).decode('utf-8')

                order = {
                    'side': side,
                    'book': message.get(55).decode('utf-8'),
                    'oid': oid,
                    'amount': order_quantity,
                    'price': message.get(44).decode('utf-8'),
                    'created_at': message.get(60).decode('utf-8')
                }
                orders.append(order)

        return orders


    @staticmethod
    def parse_trades_list(messages: List[simplefix.FixMessage]) -> List:
        orders = []

        for message in messages:

            amount_left = message.get(151).decode('utf-8')
            filled_amount = message.get(14).decode('utf-8')

            logging.debug(f"amount left: {amount_left}")
            logging.debug(f"filled amount: {filled_amount}")
            if amount_left is 0:

                # TODO: account for tag 15, currency the order is denominated in
                # TODO: account for partial order fills
                side = 'buy' if message.get(54).decode('utf-8') == 1 else 'sell'
                oid = message.get(37).decode('utf-8')

                order = {
                    'side': side,
                    'book': message.get(55).decode('utf-8'),
                    'oid': oid,
                    'amount': filled_amount,
                    'price': message.get(44).decode('utf-8'),
                    'created_at': message.get(60).decode('utf-8')
                }
                orders.append(order)

        return orders
