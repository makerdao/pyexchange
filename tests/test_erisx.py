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

import threading
import time

from pyexchange.erisx import ErisxApi
from pyexchange.fix import FixConnectionState
from tests.mock_fix_server import MockFixServer


class TestErisx:
    sender_comp_id = "unit_test"

    def setup_method(self):
        self.server = MockFixServer()
        server_thread = threading.Thread(target=self.server.run, daemon=True)
        server_thread.start()
        print(f"test setup on thread {threading.current_thread()}")

        time.sleep(1)
        self.client = ErisxApi(endpoint="127.0.0.1:1752", sender_comp_id=TestErisx.sender_comp_id,
                               username="test", password="test")
        while self.client.fix.connection_state != FixConnectionState.LOGGED_IN:
            print("waiting for login")
            time.sleep(5)

    def test_init(self):
        assert self.client.fix.senderCompId == TestErisx.sender_comp_id
        assert self.client.fix.targetCompId == "ERISX"
        assert self.client.fix.heartbeatInterval > 0

        # Wait past the heartbeatInterval and confirm heartbeats were received
        time.sleep(self.client.fix.heartbeatInterval+1)
        assert self.server.heartbeat_count > 0
