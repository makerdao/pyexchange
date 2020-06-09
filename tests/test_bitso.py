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
from pyexchange.bitso import BitsoApi, Order, Trade, iso8601_to_unix

# Models HTTP response, produced by BitsoMockServer
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
class BitsoMockServer:
    # Read JSON responses from a pipe-delimited file, avoiding JSON-inside-JSON parsing complexities
    responses = {}
    cwd = os.path.dirname(os.path.realpath(__file__))
    response_file_path = os.path.join(cwd, "mock/bitso-api-responses")
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
            return BitsoMockServer.handle_get(url)
        elif method == "POST":
            return BitsoMockServer.handle_post(url, kwargs["json"])
        else:
            return BitsoMockServer.handle_delete(url)

    @staticmethod
    def handle_get(url: str):
        # Parse the URL to determine which piece of canned data to return
        if re.search(r"v3\/available_books", url):
            return MockedResponse(text=BitsoMockServer.responses["markets"])
        elif re.search(r"v3\/balance", url):
            return MockedResponse(text=BitsoMockServer.responses["balances"])
        elif re.search(r"v3\/open_orders", url):
            return MockedResponse(text=BitsoMockServer.responses["orders"])
        elif re.search(r"v3\/user_trades", url):
            return MockedResponse(text=BitsoMockServer.responses["trades"])
        else:
            raise ValueError("Unable to match HTTP GET request to canned response", url)

    @staticmethod
    def handle_post(url: str, data):
        assert(data is not None)
        if re.search(r"v3\/orders", url):
            return MockedResponse(text=BitsoMockServer.responses["place_order"])
        else:
            raise ValueError("Unable to match HTTP POST request to canned response", url, data)

    
    @staticmethod
    def handle_delete(url: str):
        if re.search(r"v3\/orders\/[\w\-_]+", url):
            return MockedResponse(text=BitsoMockServer.responses["cancel_order"])
        else:
            raise ValueError("Unable to match HTTP DELETE request to canned response", url)

class TestBitso:
    def setup_method(self):
        self.bitso = BitsoApi(
            api_server = "localhost",
            api_key = "00000000-0000-0000-0000-000000000000",
            secret_key = "bitsosecretkey",
            timeout = 15.5
        )

    def test_convert_iso_to_unix(self):
        iso_timestamp = datetime.now(tz=timezone.utc).isoformat()
        assert(isinstance(iso_timestamp, str))

        unix_timestamp = iso8601_to_unix(iso_timestamp)
        assert(isinstance(unix_timestamp, int))

    def test_get_markets(self, mocker):
        mocker.patch("requests.request", side_effect=BitsoMockServer.handle_request)
        response = self.bitso.get_markets()
        assert(len(response) > 0)
        assert(any(x["book"] == "eth_mxn" for x in response))

    def test_order(self):
        price = Wad.from_number(4.8765)
        amount = Wad.from_number(0.222)
        remaining_amount = Wad.from_number(0.153)
        order = Order(
            order_id="153153",
            timestamp=iso8601_to_unix(datetime.now(tz=timezone.utc).isoformat()),
            pair="eth_mxn",
            is_sell=False,
            price=price,
            amount=amount
        )
        assert(order.price == order.sell_to_buy_price)
        assert(order.price == order.buy_to_sell_price)

    def test_get_balances(self, mocker):
        mocker.patch("requests.request", side_effect=BitsoMockServer.handle_request)
        response = self.bitso.get_balances()
        assert(len(response) > 0)
        for balance in response:
            if "eth" in balance["currency"]:
                assert(float(balance["total"]) > 0)

    @staticmethod
    def check_orders(orders):
        by_oid = {}
        duplicate_count = 0
        duplicate_first_found = -1
        current_time = iso8601_to_unix(datetime.now(tz=timezone.utc).isoformat())
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
        instrument_id = "eth_mxn"
        mocker.patch("requests.request", side_effect=BitsoMockServer.handle_request)
        response = self.bitso.get_orders(instrument_id)
        assert (len(response) > 0)
        for order in response:
            assert(isinstance(order.is_sell, bool))
            assert(Wad(order.price) > Wad(0))
        TestBitso.check_orders(response)

    def test_order_placement_and_cancellation(self, mocker):
        instrument_id = "eth_mxn"
        side = "sell"
        mocker.patch("requests.request", side_effect=BitsoMockServer.handle_request)
        order_id = self.bitso.place_order(instrument_id, side, 4400.000, .01)
        assert(isinstance(order_id, str))
        assert(order_id is not None)
        cancel_result = self.bitso.cancel_order(order_id)
        assert(cancel_result is True)

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
        instrument_id = "eth_mxn"
        mocker.patch("requests.request", side_effect=BitsoMockServer.handle_request)
        response = self.bitso.get_trades(instrument_id)
        assert (len(response) > 0)
        TestBitso.check_trades(response)
