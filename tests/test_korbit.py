# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway 
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
import os
import re
import time
from datetime import datetime, timezone

from pymaker import Wad
from pyexchange.korbit import KorbitApi, Order, Trade

# Models HTTP response, produced by KorbitMockServer
class MockedResponse:
    def __init__(self, text: str, status_code=200):
        assert (isinstance(text, str))
        assert (isinstance(status_code, int))
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.text = text
        self.reason = None

    def json(self, **kwargs):
        return json.loads(self.text)

# Determines response to provide based on the requested URL
class KorbitMockServer:
    # Read JSON responses from a pipe-delimited file, avoiding JSON-inside-JSON parsing complexities
    responses = {}
    cwd = os.path.dirname(os.path.realpath(__file__))
    response_file_path = os.path.join(cwd, "mock/korbit-api-responses")
    with open(response_file_path, 'r') as file:
        for line in file:
            kvp = line.split("|")
            assert(len(kvp) == 2)
            responses[kvp[0]] = kvp[1]

    @staticmethod
    def handle_request(**kwargs):
        assert("url" in kwargs)
        url = kwargs["url"]
        method = kwargs["method"]
        if method == "GET":
            return KorbitMockServer.handle_get(url)
        else:
            return KorbitMockServer.handle_post(url, kwargs["data"])

    @staticmethod
    def handle_get(url: str):
        # Parse the URL to determine which piece of canned data to return
        if re.search(r"v1\/ticker\/detailed\/all", url):
            return MockedResponse(text=KorbitMockServer.responses["markets"])
        elif re.search(r"v1\/user\/balances", url):
            return MockedResponse(text=KorbitMockServer.responses["balances"])
        elif re.search(r"v1\/user\/orders\/open", url):
            return MockedResponse(text=KorbitMockServer.responses["orders"])
        elif re.search(r"v1\/user\/transactions", url):
            return MockedResponse(text=KorbitMockServer.responses["user_trades"])
        elif re.search(r"v1\/transactions", url):
            return MockedResponse(text=KorbitMockServer.responses["all_trades"])            
        else:
            raise ValueError("Unable to match HTTP GET request to canned response", url)

    @staticmethod
    def handle_post(url: str, data):
        assert(data is not None)
        if re.search(r"v1\/user\/orders\/sell", url):
            return MockedResponse(text=KorbitMockServer.responses["single_order"])
        elif re.search(r"v1\/user\/orders\/cancel", url):
            return MockedResponse(text=KorbitMockServer.responses["cancel_order"])
        elif re.search(r"v1\/oauth2\/access_token", url):
            return MockedResponse(text=KorbitMockServer.responses["access_token"])
        else:
            raise ValueError("Unable to match HTTP POST request to canned response", url, data)


class TestKorbit:
    def setup_method(self):
        cwd = os.path.dirname(os.path.realpath(__file__))
        self.korbit = KorbitApi(
            api_server = "localhost",
            api_key = "00000000-0000-0000-0000-000000000000",
            secret_key = "secretkey",
            timeout = 15.5
        )

    def test_get_markets(self, mocker):
        mocker.patch("requests.request", side_effect=KorbitMockServer.handle_request)
        response = self.korbit.get_markets()
        assert(len(response) > 0)
        assert(response["dai_krw"] is not None)

    def test_order(self):
        price = Wad.from_number(4.8765)
        amount = Wad.from_number(0.222)
        order = Order(
            order_id="153153",
            timestamp=int(time.time()),
            pair="dai_krw",
            is_sell=False,
            price=price,
            amount=amount
        )
        assert(order.price == order.sell_to_buy_price)
        assert(order.price == order.buy_to_sell_price)

    def test_get_balances(self, mocker):
        mocker.patch("requests.request", side_effect=KorbitMockServer.handle_request)
        response = self.korbit.get_balances()
        assert(len(response) > 0)
        assert(int(response["dai"]["available"]) > 0)

    @staticmethod
    def check_orders(orders):
        by_oid = {}
        duplicate_count = 0
        duplicate_first_found = -1
        current_time = int(time.time() * 1000)
        for index, order in enumerate(orders):
            assert(isinstance(order, Order))
            assert(order.order_id is not None)
            assert(order.timestamp < current_time)

            # Check for duplicates
            if order.order_id in by_oid:
                duplicate_count += 1
                if duplicate_first_found < 0:
                    duplicate_first_found = index
            else:
                by_oid[order.order_id] = order

        if duplicate_count > 0:
            print(f"{duplicate_count} duplicate orders were found, "
                  f"starting at index {duplicate_first_found}")
        else:
            print("no duplicates were found")
        assert(duplicate_count == 0)
        
    def test_get_orders(self, mocker):
        pair = "dai_krw"
        mocker.patch("requests.request", side_effect=KorbitMockServer.handle_request)
        response = self.korbit.get_orders(pair)
        assert (len(response) > 0)
        for order in response:
            assert(isinstance(order.is_sell, bool))
            assert(Wad(order.price) > Wad(0))
        TestKorbit.check_orders(response)

    def test_order_placement_and_cancellation(self, mocker):
        pair = "dai_krw"
        side = "ask"
        mocker.patch("requests.request", side_effect=KorbitMockServer.handle_request)
        order_id = self.korbit.place_order(pair, True, Wad.from_number(1500), Wad.from_number(10))
        assert(isinstance(order_id, int))
        assert(order_id is not None)
        cancel_result = self.korbit.cancel_order(order_id, pair)
        assert(cancel_result == True)

    @staticmethod
    def check_trades(trades):
        by_tradeid = {}
        duplicate_count = 0
        duplicate_first_found = -1
        missorted_found = False
        last_timestamp = 0
        for index, trade in enumerate(trades):
            assert(isinstance(trade, Trade))
            if trade.trade_id in by_tradeid:
                print(f"found duplicate trade {trade.trade_id}")
                duplicate_count += 1
                if duplicate_first_found < 0:
                    duplicate_first_found = index
            else:
                by_tradeid[trade.trade_id] = trade
                if not missorted_found and last_timestamp > 0:
                    if trade.timestamp > last_timestamp:
                        print(f"missorted trade found at index {index}")
                        missorted_found = True
                    last_timestamp = trade.timestamp
        if duplicate_count > 0:
            print(f"{duplicate_count} duplicate trades were found, "
                  f"starting at index {duplicate_first_found}")
        else:
            print("no duplicates were found")
        assert(duplicate_count == 0)
        assert(missorted_found is False)

    def test_get_trades(self, mocker):
        pair = "dai_krw"
        mocker.patch("requests.request", side_effect=KorbitMockServer.handle_request)
        response = self.korbit.get_trades(pair)
        assert (len(response) > 0)
        TestKorbit.check_trades(response)

    def test_get_all_trades(self, mocker):
        pair = "bat_krw"
        mocker.patch("requests.request", side_effect=KorbitMockServer.handle_request)
        response = self.korbit.get_all_trades(pair)
        assert (len(response) > 0)
        TestKorbit.check_trades(response)
