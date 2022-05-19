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
import time
import pytest
from pyflex import Wad
from pyexchange.dydx import DydxApi, Order, Trade

# Even though DyDx is a Decentralized Exchange,
# supporting infrastructure required for the orderbook is only available on mainnet.
# Therefore, mock data was used.

# Models HTTP response, produced by DydxMockServer
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

# Determines response based upon the DyDx Client method used
class DydxMockServer:
    # Read JSON responses from a pipe-delimited file, avoiding JSON-inside-JSON parsing complexities
    responses = {}
    cwd = os.path.dirname(os.path.realpath(__file__))
    response_file_path = os.path.join(cwd, "mock/dydx-api-responses")
    with open(response_file_path, 'r') as file:
        for line in file:
            kvp = line.split("|")
            assert(len(kvp) == 2)
            responses[kvp[0]] = kvp[1]

    @staticmethod
    def handle_get_pairs(**kwargs):
        return MockedResponse(text=DydxMockServer.responses["markets"]).json()

    @staticmethod
    def handle_get_balances(*args, **kwargs):
        return MockedResponse(text=DydxMockServer.responses["balances"]).json()

    @staticmethod
    def handle_get_orders(**kwargs):
        return MockedResponse(text=DydxMockServer.responses["orders"]).json()

    @staticmethod
    def handle_place_order(**kwargs):
        return MockedResponse(text=DydxMockServer.responses["place_order"]).json()

    @staticmethod
    def handle_cancel_order(**kwargs):
        return MockedResponse(text=DydxMockServer.responses["cancel_order"]).json()

    @staticmethod
    def handle_get_trades(**kwargs):
        return MockedResponse(text=DydxMockServer.responses["trades"]).json()

@pytest.mark.skip("deprecated?")
class TestDydx:
    def setup_method(self):
        self.dydx = DydxApi(
            "http://localhost:8555",
            "dcba44978751342a68e81b0e487de87e52720f6f94792cc237045bce0f9d05fc"
        )

    def test_get_markets(self, mocker):
        mocker.patch("dydx.client.Client.get_markets", side_effect=DydxMockServer.handle_get_pairs)
        response = self.dydx.get_markets()
        assert(len(response) > 0)
        assert("WETH-DAI" in response)

    def test_order(self):
        price = Wad.from_number(4.8765)
        amount = Wad.from_number(0.222)
        remaining_amount = Wad.from_number(0.153)
        order = Order(
            order_id="153153",
            timestamp=int(time.time()),
            pair="WETH-DAI",
            is_sell=False,
            price=price,
            amount=amount
        )
        assert(order.price == order.sell_to_buy_price)
        assert(order.price == order.buy_to_sell_price)

    def test_get_balances(self, mocker):
        mocker.patch("dydx.client.Client.get_balances", side_effect=DydxMockServer.handle_get_balances)
        response = self.dydx.get_balances()
        assert(len(response) > 0)
        for balance in response:
            if "ETH" in balance["currency"]:
                assert(float(balance["wei"]) > 0)

    @staticmethod
    def check_orders(orders):
        by_oid = {}
        duplicate_count = 0
        duplicate_first_found = -1
        current_time = int(time.time())
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
        instrument_id = "WETH-DAI"
        mocker.patch("dydx.client.Client.get_my_orders", side_effect=DydxMockServer.handle_get_orders)
        response = self.dydx.get_orders(instrument_id)
        assert (len(response) > 0)
        for order in response:
            assert(isinstance(order.is_sell, bool))
            assert(Wad(order.price) > Wad(0))
        TestDydx.check_orders(response)

    def test_order_placement_and_cancellation(self, mocker):
        instrument_id = "WETH-DAI"
        side = "sell"
        mocker.patch("dydx.client.Client.place_order", side_effect=DydxMockServer.handle_place_order)
        mocker.patch("dydx.client.Client.cancel_order", side_effect=DydxMockServer.handle_cancel_order)
        order_id = self.dydx.place_order(instrument_id, False, 135.000, 0.1)
        assert(isinstance(order_id, str))
        assert(order_id is not None)
        cancel_result = self.dydx.cancel_order(order_id)
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
        instrument_id = "WETH-DAI"
        mocker.patch("dydx.client.Client.get_my_fills", side_effect=DydxMockServer.handle_get_trades)
        response = self.dydx.get_trades(instrument_id)
        assert (len(response) > 0)
        TestDydx.check_trades(response)
