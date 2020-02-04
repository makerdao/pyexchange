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
import threading

from enum import Enum


class FixConnectionState(Enum):
    UNKNOWN = 0
    DISCONNECTED = 1
    CONNECTED = 2
    LOGGED_IN = 3
    LOGGED_OUT = 4


class FixEngine:
    """Enables interfacing with exchanges using the FIX (Financial Information eXchange) protocol.
    This class shall implement common logic for connection management and fulfill relevant functions from PyexAPI.

    Ideally, subclasses should not need to import simplefix, insulating them from implementation logic within.
    Note that simplefix automatically populates fields 9 (message length) and 10 (checksum)."""

    logger = logging.getLogger()

    def __init__(self, endpoint: str, sender_comp_id: str, target_comp_id: str, username: str, password: str,
                 fix_version="FIX.4.4", heartbeat_interval=3):
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
        self.fix_version = fix_version
        self.heartbeat_interval = heartbeat_interval
        self.sequenceNum = 0
        self.connection_state = FixConnectionState.DISCONNECTED

        self.reader = None
        self.writer = None
        self.parser = simplefix.FixParser()

        self.loop = None
        self.heartbeat_loop = None

    async def _read_message(self):
        """Reads the next message from the server"""
        try:
            message = None
            while message is None:
                await asyncio.sleep(0)
                buf = await self.reader.read()
                if not buf:
                    raise ConnectionError
                self.parser.append_buffer(buf)
                message = self.parser.get_message()
            logging.debug(f"client received message {message}")
            return message
        except asyncio.CancelledError:
            logging.error("client read timed out")
            assert False

    async def _write_message(self, message: simplefix.FixMessage):
        """Sends a message to the server"""
        logging.debug(f"client sending message {message}")
        self.writer.write(message.encode())
        await self.writer.drain()
        logging.debug("client done sending message")

    def create_message(self, message_type: str) -> simplefix.FixMessage:
        assert isinstance(message_type, str)
        assert len(message_type) == 1

        m = simplefix.FixMessage()
        m.append_pair(8, self.fix_version)
        m.append_pair(35, message_type)
        m.append_pair(49, self.senderCompId)
        m.append_pair(56, self.targetCompId)
        return m

    def logon(self):
        # Synchronously establish a connection with the remote endpoint
        (address, port) = tuple(self.endpoint.split(':'))
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.reader, self.writer = self.loop.run_until_complete(asyncio.open_connection(address, port, loop=self.loop))
        self.connection_state = FixConnectionState.CONNECTED

        # Start a thread and loop to asynchronously send heartbeats while we are logged in
        self.heartbeat_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        heartbeat_thread = threading.Thread(target=self.run_heartbeats, daemon=True)
        heartbeat_thread.start()

        """Synchronously send a logon message and await its acknowledgement"""
        m = self.create_message('A')
        self._append_sequence_number(m)
        m.append_utc_timestamp(52, header=True)
        m.append_pair(98, '0')
        m.append_pair(108, self.heartbeat_interval)
        m.append_pair(141, 'Y')
        m.append_pair(553, self.username)
        m.append_pair(554, self.password)
        self.loop.run_until_complete(asyncio.wait_for(self._write_message(m), 10))

        # Confirm logon request (35=A) is acknowledged
        logging.debug("awaiting logon response")
        message = self.loop.run_until_complete(asyncio.wait_for(self._read_message(), 30))
        assert message.get(35) == b'A'
        self.connection_state = FixConnectionState.LOGGED_IN
        logging.debug("client logon complete")

    def logout(self):
        # Send a logout message
        m = self.create_message('5')
        try:
            self.loop.run_until_complete(asyncio.wait_for(self._write_message(m), 3))
        except ConnectionResetError:
            # Ignore heartbeats sent while disconnecting
            pass
        finally:
            self.connection_state = FixConnectionState.LOGGED_OUT

    def run_heartbeats(self):
        self.heartbeat_loop.run_until_complete(self._heartbeat())

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            if self.connection_state != FixConnectionState.LOGGED_IN:
                logging.debug("client not logged in; skipping heartbeat")
                continue
            m = self.create_message('0')
            self._append_sequence_number(m)
            await self._write_message(m)
            logging.debug("client sent heartbeat")

    def _append_sequence_number(self, m: simplefix.FixMessage):
        assert isinstance(m, simplefix.FixMessage)
        self.sequenceNum += 1
        m.append_pair(34, self.sequenceNum, header=True)
