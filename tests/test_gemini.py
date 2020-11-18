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

import re
import time

import pytest

from pymaker import Wad
from pyexchange.gemini import GeminiApi, GeminiOrder as Order, GeminiTrade as Trade
from tests.mock_webapi_server import MockWebAPIServer, MockedResponse


class GeminiMockServer(MockWebAPIServer):

    def __init__(self):
        super().__init__("mock/gemini-api-responses")

    def handle_request(self, **kwargs):
        assert ("url" in kwargs)
        url = kwargs["url"]
        method = kwargs["method"]
        if method == "GET":
            return self.handle_get(url)
        elif method == "POST":
            return self.handle_post(url, kwargs["headers"])
        else:
            raise ValueError("Unable to match HTTP method")

    def handle_get(self, url: str):
        # Parse the URL to determine which piece of canned data to return
        if re.search(r"\/v1\/trades", url):
            return MockedResponse(text=self.responses["allTrades"])
        elif re.search(r"\/v1\/symbols\/details", url):
            return MockedResponse(text=self.responses["symbolDetails"])
        else:
            raise ValueError("Unable to match HTTP GET request to canned response", url)

    def handle_post(self, url: str, params):
        assert (params is not None)
        if re.search(r"\/v1\/balances", url):
            return MockedResponse(text=self.responses["balances"])
        elif re.search(r"\/v1\/orders", url):
            return MockedResponse(text=self.responses["orders"])
        elif re.search(r"\/v1\/order\/new", url):
            return MockedResponse(text=self.responses["orderNew"])
        elif re.search(r"\/v1\/order\/cancel", url):
            return MockedResponse(text=self.responses["orderCancel"])
        elif re.search(r"\/v1\/mytrades", url):
            return MockedResponse(text=self.responses["myTrades"])
        else:
            raise ValueError("Unable to match HTTP POST request to canned response", url, params)
    

class TestGemini:
    def setup_method(self):
        self.gemini = GeminiApi(
            api_server="localhost",
            api_key="00000000-0000-0000-0000-000000000000",
            api_secret="secretkey",
            timeout=15.5
        )
        self.GeminiMockServer = GeminiMockServer()


    def test_order(self):
        price = Wad.from_number(4.8765)
        amount = Wad.from_number(0.222)
        order = Order(
            order_id="153153",
            timestamp=int(time.time()),
            pair="DAI-ETH",
            is_sell=False,
            price=price,
            amount=amount
        )
        assert (order.price == order.sell_to_buy_price)
        assert (order.price == order.buy_to_sell_price)

    def test_get_balances(self, mocker):
        mocker.patch("requests.request", side_effect=self.GeminiMockServer.handle_request)
        response = self.gemini.get_balances()
        
        eth_balance = response["ETH"]
        btc_balance = response["BTC"]

        assert (len(response) > 0)
        assert (float(btc_balance['amount']) > 100)
        assert(float(btc_balance["availableForTrade"]) > 80)

        assert (float(eth_balance['amount']) > 17)
        assert(float(eth_balance["availableForTrade"]) > 10)

    @staticmethod
    def check_orders(orders):
        by_oid = {}
        duplicate_count = 0
        duplicate_first_found = -1
        current_time = int(time.time() * 1000)
        for index, order in enumerate(orders):
            assert (isinstance(order, Order))
            assert (order.order_id is not None)
            assert (order.timestamp < current_time)

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
        assert (duplicate_count == 0)

    def test_get_orders(self, mocker):
        pair = "DAI-ETH"
        mocker.patch("requests.request", side_effect=self.GeminiMockServer.handle_request)
        response = self.gemini.get_orders(pair)
        assert (len(response) > 0)
        for order in response:
            assert (isinstance(order.is_sell, bool))
            assert (Wad(order.price) > Wad(0))
        TestGemini.check_orders(response)

    def test_order_placement_and_cancellation(self, mocker):
        pair = "DAI-ETH"
        side = "ask"
        mocker.patch("requests.request", side_effect=self.GeminiMockServer.handle_request)
        order_id = self.gemini.place_order(pair, True, Wad.from_number(241700), Wad.from_number(10))
        assert (isinstance(order_id, str))
        assert (order_id is not None)
        cancel_result = self.gemini.cancel_order(order_id)
        assert (cancel_result == True)

    @staticmethod
    def check_trades(trades):
        by_tradeid = {}
        duplicate_count = 0
        duplicate_first_found = -1
        missorted_found = False
        last_timestamp = 0
        for index, trade in enumerate(trades):
            assert (isinstance(trade, Trade))
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
        assert (duplicate_count == 0)
        assert (missorted_found is False)

    def test_get_trades(self, mocker):
        pair = "DAI-ETH"
        mocker.patch("requests.request", side_effect=self.GeminiMockServer.handle_request)
        response = self.gemini.get_trades(pair)
        assert (len(response) > 0)
        TestGemini.check_trades(response)
   

    def test_get_rules(self, mocker):
        pair = "ETH-DAI"
        mocker.patch("requests.request", side_effect=self.GeminiMockServer.handle_request)
        minimum_order_size, tick_size, quote_currency_price_increment = self.gemini.get_rules(pair)

        assert tick_size == Wad.from_number(2)
        assert quote_currency_price_increment == Wad.from_number(6)
        assert minimum_order_size == Wad.from_number("0.001")
   