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
from pyexchange.fix import FixConnectionState
from tests.mock_fix_server import MockFixServer
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


class TestErisx:
    def setup_method(self):
        # self.fix_server = MockFixServer()
        # self.fix_server.run_in_another_thread()
        # time.sleep(1)
        self.clearing_server = ErisXMockClearingAPIServer()

        self.client = ErisxApi(fix_trading_endpoint="127.0.0.1:1752", fix_trading_user="test",
                               fix_marketdata_endpoint="127.0.0.1:1753", fix_marketdata_user="test",
                               password="test",
                               clearing_url="https://clearing.newrelease.erisx.com/api/v1/",
                               api_key="key", api_secret="secret")
        # while self.client.fix.connection_state != FixConnectionState.LOGGED_IN:
        #     print("waiting for login")
        #     time.sleep(5)

    def test_init(self):
        assert self.client.fix_trading.senderCompId == "test"
        assert self.client.fix_trading.targetCompId == "ERISX"
        assert self.client.fix_trading.heartbeat_interval > 0
        assert self.client.fix_marketdata.senderCompId == "test"
        assert self.client.fix_marketdata.targetCompId == "ERISX"
        assert self.client.fix_marketdata.heartbeat_interval > 0

    @pytest.mark.skip("mock FIX server remains under construction")
    def test_heartbeats(self):
        # Wait past the heartbeatInterval and confirm heartbeats were received
        time.sleep(self.client.fix_trading.heartbeat_interval*10)
        assert self.client.fix_trading.sequenceNum > 2

    def test_get_balances(self, mocker):
        mocker.patch("requests.post", side_effect=self.clearing_server.handle_request)
        response = self.client.get_balances()
        assert (len(response) > 0)
        assert ("account_id" in response[0])
        assert ("account_number" in response[0])
        assert ("balances" in response[0])
