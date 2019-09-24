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

import asyncio
import logging
import simplefix
import socket

from pyexchange.api import PyexAPI


class FixEngine(PyexAPI):
    """Abstract baseclass to use with exchanges with we interface with using the FIX
    (Financial Information eXchange) protocol.  This class shall implement common logic for connection management
    and fulfill interface contracts presented by PyexAPI.

    Ideally, subclasses should not need to import simplefix, insulating them from implementation logic within.
    Note that simplefix automatically populates fields 9 (message length) and 10 (checksum)."""

    logger = logging.getLogger()

    def __init__(self, endpoint: str, sender_comp_id: str, target_comp_id: str, username: str, password: str,
                 fix_version="FIX.4.4", heartbeat_interval=10):
        assert isinstance(endpoint, str)
        assert isinstance(sender_comp_id, str)
        assert isinstance(target_comp_id, str)
        assert isinstance(username, str)
        assert isinstance(password, str)

        self.endpoint = endpoint
        self.senderCompId = sender_comp_id
        self.targetCompId = target_comp_id
        self.username = username
        self.password = password
        self.fixVersion = fix_version
        self.heartbeatInterval = heartbeat_interval
        self.sequenceNum = 0

        self._heartbeatTask = None
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        (address, port) = tuple(endpoint.split(':'))
        print(f"connecting to {address} on port {int(port)}")
        self.s.connect((address, int(port)))
        # TODO: Upon receipt of logon message (35=A), start Lifecycle timer to send heartbeats (35=0)

    def logon(self):
        m = simplefix.FixMessage()
        m.append_pair(8, self.fixVersion)
        m.append_pair(35, 'A')
        m.append_pair(49, self.senderCompId)
        m.append_pair(56, self.targetCompId)
        self._append_sequence_number(m)
        m.append_utc_timestamp(52, header=True)
        m.append_pair(98, '0')
        m.append_pair(108, self.heartbeatInterval)
        m.append_pair(141, 'Y')
        m.append_pair(553, self.username)
        m.append_pair(554, self.password)
        self.s.sendall(m.encode())

        if self._heartbeatTask is None:
            self._heartbeatTask = asyncio.ensure_future(self._heartbeat())

    def logoff(self):
        self._heartbeatTask.cancel()
        self._heartbeatTask = None

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(self.heartbeatInterval)
            m = simplefix.FixMessage()
            m.append_pair(35, '0')
            self.s.sendall(m.encode())

    def _append_sequence_number(self, m: simplefix.FixMessage):
        assert isinstance(m, simplefix.FixMessage)
        self.sequenceNum += 1
        m.append_pair(34, self.sequenceNum, header=True)

    def ticker(self, pair):
        raise NotImplementedError()

    def get_markets(self):
        raise NotImplementedError()

    def get_pair(self, pair):
        raise NotImplementedError()

    def get_balances(self):
        raise NotImplementedError()

    def get_orders(self, pair):
        raise NotImplementedError()

    def place_order(self, pair, is_sell, price, amount):
        # TODO: Send 35=D
        raise NotImplementedError()

    def cancel_order(self, order_id):
        # TODO: Send 35=F
        raise NotImplementedError()

    def get_trades(self, pair, page_number):
        raise NotImplementedError()

    def get_all_trades(self, pair, page_number):
        # TODO:
        raise NotImplementedError()
