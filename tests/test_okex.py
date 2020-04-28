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
import os
import re
import time

from pymaker import Wad
from pyexchange.model import Candle
from pyexchange.okex import Order
from pyexchange.okex import Trade
from pyexchange.okex import OKEXApi

# Models HTTP response, produced by OkexMockServer
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
class OkexMockServer:
    # Read JSON responses from a pipe-delimited file, avoiding JSON-inside-JSON parsing complexities
    responses = {}
    cwd = os.path.dirname(os.path.realpath(__file__))
    response_file_path = os.path.join(cwd, "mock/okex-api-responses")
    with open(response_file_path, 'r') as file:
        for line in file:
            kvp = line.split("|")
            assert(len(kvp) == 2)
            responses[kvp[0]] = kvp[1]

    @staticmethod
    def handle_request(**kwargs):
        assert("url" in kwargs)
        url = kwargs["url"]
        if "data" not in kwargs:
            return OkexMockServer.handle_get(url)
        else:
            return OkexMockServer.handle_post(url, kwargs["data"])

    @staticmethod
    def handle_get(url: str):
        # Parse the URL to determine which piece of canned data to return
        if re.search(r"api\/spot\/v3\/instruments\/[\w\-_]+\/ticker", url):
            return MockedResponse(text=OkexMockServer.responses["ticker1"])
        elif re.search(r"api\/spot\/v3\/instruments\/[\w\-_]+\/book", url):
            return MockedResponse(text=OkexMockServer.responses["book1"])
        elif re.search(r"api\/spot\/v3\/instruments\/[\w\-_]+\/candles", url):
            return MockedResponse(text=OkexMockServer.responses["candles1"])
        elif "/api/spot/v3/accounts" in url:
            return MockedResponse(text=OkexMockServer.responses["accounts1"])
        elif "/api/spot/v3/orders_pending" in url:
            return MockedResponse(text=OkexMockServer.responses["orders1"])
        elif re.search(r"\/api\/spot\/v3\/orders\?state=[\w_%]+&instrument_id=[\w\-_]+&limit=\d+", url):
            return MockedResponse(text=OkexMockServer.responses["orders2"])
        elif re.search(r"\/api\/spot\/v3\/orders\?state=1&instrument_id=[\w\-_]+", url):
            return MockedResponse(text="[]")  # assume no partial fills
        elif re.search(r"\/api\/spot\/v3\/orders\?state=2&instrument_id=[\w\-_]+", url):
            return MockedResponse(text=OkexMockServer.responses["trades1"])
        elif re.search(r"\/api\/spot\/v3\/instruments\/[\w\-_]+\/trades", url):
            return MockedResponse(text=OkexMockServer.responses["trades2"])
        else:
            raise Exception("Unable to match HTTP GET request to canned response")

    @staticmethod
    def handle_post(url: str, data):
        assert(data is not None)
        if "/api/spot/v3/orders" in url:
            return MockedResponse(text=OkexMockServer.responses["place_order1"])
        elif "/api/spot/v3/cancel_orders" in url:
            return MockedResponse(text=OkexMockServer.responses["cancel_order1"])
        else:
            raise Exception("Unable to match HTTP POST request to canned response")


class TestOKEX:
    def setup_method(self):
        self.okex = OKEXApi(
            api_server = "localhost",
            api_key = "00000000-0000-0000-0000-000000000000",
            secret_key = "DEAD000000000000000000000000DEAD",
            password = "password to nonexistant account",
            timeout = 15.5
        )

    def test_order(self):
        price = Wad.from_number(4.8765)
        amount = Wad.from_number(0.222)
        filled_amount = Wad.from_number(0.153)
        order = Order(
            order_id="153153",
            timestamp=int(time.time()),
            pair="MKR-ETH",
            is_sell=False,
            price=price,
            amount=amount,
            filled_amount=filled_amount
        )
        assert(order.price == order.sell_to_buy_price)
        assert(order.price == order.buy_to_sell_price)
        assert(order.remaining_buy_amount == amount-filled_amount)
        assert(order.remaining_sell_amount == (amount-filled_amount)*price)

    def test_ticker(self, mocker):
        pair = "mkr_usdt"
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.ticker(pair)
        assert(str(response["instrument_id"]).lower().replace('-', '_') == pair)
        assert(float(response["best_ask"]) > 0)
        assert(response["instrument_id"] == response["product_id"])

    def test_depth(self, mocker):
        pair = "mkr_usdt"
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.depth(pair)
        assert("bids" in response)
        assert("asks" in response)
        assert(len(response["bids"]) > 0)
        assert(len(response["asks"]) > 0)

    def test_candles(self, mocker):
        pair = "mkr_usdt"
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.candles(pair, "1min")
        assert(len(response) > 0)
        for item in response:
            assert(isinstance(item, Candle))
            assert(item.timestamp > 0)
            assert(float(item.open) > 0)
            assert(float(item.high) > 0)
            assert(float(item.low) > 0)
            assert(float(item.close) > 0)

    def test_get_balances(self, mocker):
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.get_balances()
        assert(len(response) > 0)
        assert("MKR" in response)
        assert("ETH" in response)

    @staticmethod
    def check_orders(orders):
        by_oid = {}
        duplicate_count = 0
        duplicate_first_found = -1
        missorted_found = False
        last_timestamp = 0
        for index, order in enumerate(orders):
            assert(isinstance(order, Order))
            assert(order.order_id is not None)
            assert(order.timestamp > 0)
            # An order cannot be filled for more than the order amount
            assert(order.filled_amount <= order.amount)

            # Check for duplicates and missorted orders
            if order.order_id in by_oid:
                duplicate_count += 1
                if duplicate_first_found < 0:
                    duplicate_first_found = index
            else:
                by_oid[order.order_id] = order
                if not missorted_found and last_timestamp > 0:
                    if order.timestamp > last_timestamp:
                        print(f"missorted order found at index {index}")
                        missorted_found = True
                last_timestamp = order.timestamp

        if duplicate_count > 0:
            print(f"{duplicate_count} duplicate orders were found, "
                  f"starting at index {duplicate_first_found}")
        else:
            print("no duplicates were found")
        assert(duplicate_count == 0)
        assert(missorted_found is False)

    def test_get_orders(self, mocker):
        pair = "mkr_eth"
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.get_orders(pair)
        assert (len(response) > 0)
        for order in response:
            # Open orders cannot be completed filled
            assert(order.filled_amount < order.amount)
            assert(isinstance(order.is_sell, bool))
            assert(order.price > Wad(0))
        TestOKEX.check_orders(response)

    def test_get_all_orders(self, mocker):
        pair = "mkr_eth"
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.get_orders_history(pair, 99)
        assert (len(response) > 0)
        for order in response:
            assert(isinstance(order.is_sell, bool))
            assert(order.price > Wad(0))
        TestOKEX.check_orders(response)

    def test_order_placement_and_cancellation(self, mocker):
        pair = "mkr_usdt"
        mocker.patch("requests.post", side_effect=OkexMockServer.handle_request)
        order_id = self.okex.place_order(pair, True, Wad.from_number(639.3), Wad.from_number(0.15))
        assert(isinstance(order_id, str))
        assert(order_id is not None)
        cancel_result = self.okex.cancel_order(pair, order_id)
        assert(cancel_result)

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
        pair = "mkr_eth"
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.get_trades(pair)
        assert (len(response) > 0)
        TestOKEX.check_trades(response)

    def test_get_all_trades(self, mocker):
        pair = "mkr_usdt"
        mocker.patch("requests.get", side_effect=OkexMockServer.handle_request)
        response = self.okex.get_all_trades(pair)
        assert (len(response) > 0)
        TestOKEX.check_trades(response)
