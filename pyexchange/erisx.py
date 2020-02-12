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

from pyexchange.api import PyexAPI
from pyexchange.fix import FixEngine
from pymaker.util import http_response_summary


class ErisxApi(PyexAPI):
    """Implementation logic for interacting with the ErisX exchange, which uses FIX for order management and
    market data, and a WebAPI for retrieving account balances."""

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
        # self.fix_trading.logon()
        self.fix_marketdata = ErisxFix(fix_marketdata_endpoint, fix_marketdata_user, fix_trading_user, password)
        self.fix_marketdata.logon()

        self.clearing_url = clearing_url
        self.api_secret = api_secret
        self.api_key = api_key

    def __del__(self):
        self.fix_marketdata.logout()

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

    def get_pair(self, pair):
        # TODO: receive a 35=f (not sure how to request it)
        raise NotImplementedError()

    def get_balances(self):
        # Call into the /accounts method of ErisX Clearing WebAPI, which provides a balance of each coin.
        # They also offer a detailed /balances API, which I don't believe we need at this time.
        response = self._http_post("accounts", {})
        if "accounts" in response:
            return response["accounts"]
        else:
            raise RuntimeError("Couldn't interpret response")

    def get_orders(self, pair):
        # TODO: Send 35=MA, await 35=8, map the executions by tag 37 (OrderID) to build order state
        raise NotImplementedError()

    def place_order(self, pair, is_sell, price, amount):
        # TODO: Send 35=D; await the execution report confirming order is placed
        raise NotImplementedError()

    def cancel_order(self, order_id):
        # TODO: Send 35=F
        raise NotImplementedError()

    def get_trades(self, pair, page_number):
        # TODO: like get_orders, send a 35=MA, filter out any open orders (not partially filled)
        raise NotImplementedError()

    def get_all_trades(self, pair, page_number):
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
                          data=json.dumps(params),
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
                                       username=username, password=password, fix_version="FIX.4.4", heartbeat_interval=10)
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