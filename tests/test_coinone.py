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

import re
import time

from pymaker import Wad
from pyexchange.coinone import CoinoneApi, Order, Trade
from tests.mock_webapi_server import MockWebAPIServer, MockedResponse


class CoinoneMockServer(MockWebAPIServer):

    def __init__(self):
        super().__init__("mock/coinone-api-responses")

    def handle_request(self, **kwargs):
        assert ("url" in kwargs)
        url = kwargs["url"]
        method = kwargs["method"]
        if method == "GET":
            return self.handle_get(url)
        else:
            return self.handle_post(url, kwargs["data"])

    def handle_get(self, url: str):
        # Parse the URL to determine which piece of canned data to return
        if re.search(r"orderbook", url):
            return MockedResponse(text=self.responses["markets"])
        else:
            raise ValueError("Unable to match HTTP GET request to canned response", url)

    def handle_post(self, url: str, data):
        assert (data is not None)
        if re.search(r"v2\/account\/balance", url):
            return MockedResponse(text=self.responses["balances"])
        elif re.search(r"v2\/order\/limit_orders", url):
            return MockedResponse(text=self.responses["orders"])
        elif re.search(r"v2\/order\/limit_sell", url):
            return MockedResponse(text=self.responses["single_order"])
        elif re.search(r"v2\/order\/cancel", url):
            return MockedResponse(text=self.responses["cancel_order"])
        elif re.search(r"v2\/order\/complete_orders", url):
            return MockedResponse(text=self.responses["trades"])
        else:
            raise ValueError("Unable to match HTTP POST request to canned response", url, data)


class TestCoinone:
    def setup_method(self):
        self.coinone = CoinoneApi(
            api_server="localhost",
            access_token="00000000-0000-0000-0000-000000000000",
            secret_key="secretkey",
            timeout=15.5
        )
        self.coinoneMockServer = CoinoneMockServer()

    def test_get_markets(self, mocker):
        mocker.patch("requests.request", side_effect=self.coinoneMockServer.handle_request)
        response = self.coinone.get_markets()
        assert (len(response) > 0)
        # assert (response["eth"] is not None)

    def test_order(self):
        price = Wad.from_number(4.8765)
        amount = Wad.from_number(0.222)
        order = Order(
            order_id="153153",
            timestamp=int(time.time()),
            pair="ETH-KRW",
            is_sell=False,
            price=price,
            amount=amount
        )
        assert (order.price == order.sell_to_buy_price)
        assert (order.price == order.buy_to_sell_price)

    def test_get_balances(self, mocker):
        mocker.patch("requests.request", side_effect=self.coinoneMockServer.handle_request)
        response = self.coinone.get_balances()
        assert (len(response) > 0)
        assert (float(response["eth"]["avail"]) > 0)

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
        pair = "ETH-KRW"
        mocker.patch("requests.request", side_effect=self.coinoneMockServer.handle_request)
        response = self.coinone.get_orders(pair)
        assert (len(response) > 0)
        for order in response:
            assert (isinstance(order.is_sell, bool))
            assert (Wad(order.price) > Wad(0))
        TestCoinone.check_orders(response)

    def test_order_placement_and_cancellation(self, mocker):
        pair = "ETH-KRW"
        side = "ask"
        mocker.patch("requests.request", side_effect=self.coinoneMockServer.handle_request)
        order_id = self.coinone.place_order(pair, True, Wad.from_number(241700), Wad.from_number(10))
        assert (isinstance(order_id, str))
        assert (order_id is not None)
        cancel_result = self.coinone.cancel_order(order_id, pair,  Wad.from_number(241700), Wad.from_number(10), True)
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
        pair = "ETH-KRW"
        mocker.patch("requests.request", side_effect=self.coinoneMockServer.handle_request)
        response = self.coinone.get_trades(pair)
        assert (len(response) > 0)
        TestCoinone.check_trades(response)

