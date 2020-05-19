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

import pytest
import time

from pyexchange.erisx import ErisxApi
from pyexchange.fix import FixEngine
from pyexchange.model import Trade
from tests.mock_webapi_server import MockedResponse, MockWebAPIServer


class ErisXMockClearingAPIServer(MockWebAPIServer):
    def __init__(self):
        super(ErisXMockClearingAPIServer, self).__init__("mock/erisx-clearing-api-responses")

    def handle_get(self, url: str):
        """No GET requests are needed to interact with ErisX Clearing API"""
        assert False

    def handle_post(self, url: str, data):
        if "accounts" in url:
            return MockedResponse(text=self.responses["accounts1"])
        elif "balances" in url:
            return MockedResponse(text=self.responses["balances"])
        elif "trades" in url:
            return MockedResponse(text=self.responses["trades"])


class TestErisx:
    def setup_method(self):
        self.clearing_server = ErisXMockClearingAPIServer()
        do_nothing = lambda *args: None

        orig_get_account = ErisxApi.get_account
        FixEngine.logon = do_nothing
        ErisxApi.get_account = do_nothing
        self.account_id = 0
        self.client = ErisxApi(fix_trading_endpoint="127.0.0.1:1752", fix_trading_user="test",
                               fix_marketdata_endpoint="127.0.0.1:1753", fix_marketdata_user="test",
                               password="test",
                               clearing_url="https://127.0.0.1/api/v1/",
                               api_key="key", api_secret="secret", certs=None, account_id=self.account_id)
        ErisxApi.get_account = orig_get_account

    def test_init(self):
        assert self.client.fix_trading.senderCompId == "test"
        assert self.client.fix_trading.targetCompId == "ERISX"
        assert self.client.fix_trading.heartbeat_interval > 0
        assert self.client.fix_marketdata.senderCompId == "test"
        assert self.client.fix_marketdata.targetCompId == "ERISX"
        assert self.client.fix_marketdata.heartbeat_interval > 0

    @pytest.mark.skip("FIX simulation engine needed")
    def test_heartbeats(self):
        # Wait past the heartbeatInterval and confirm heartbeats were received
        time.sleep(self.client.fix_trading.heartbeat_interval*10)
        assert self.client.fix_trading.sequenceNum > 2

    def test_get_account(self, mocker):
        mocker.patch("requests.post", side_effect=self.clearing_server.handle_request)
        response = self.client.get_account(self.account_id)
        assert (len(response) > 0)
        assert(response == "27ff6d34-523d-476d-9ad5-edeb373b83dc")

    def test_get_balances(self, mocker):
        mocker.patch("requests.post", side_effect=self.clearing_server.handle_request)
        response = self.client.get_balances()
        assert (len(response) > 0)
        assert isinstance(response, dict)
        assert response["account_id"] == "27ff6d34-523d-476d-9ad5-edeb373b83dc"
        balances_for_account = response["balances"]
        print(f"balances {type(response)} {response}")
        for balance in balances_for_account:
            assert isinstance(balance, dict)
            if balance["asset_type"] == "TETH":
                assert(float(balance["available_to_trade"]) == 12.6)

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
        pair = "ETH/USD"
        mocker.patch("requests.post", side_effect=self.clearing_server.handle_request)
        response = self.client.get_trades(pair)
        assert (len(response) > 0)
        print(f"trades: {response}")
        TestErisx.check_trades(response)
