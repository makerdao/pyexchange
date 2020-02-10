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
import time
import queue
import threading
from datetime import datetime, timedelta
from enum import Enum


class FixConnectionState(Enum):
    UNKNOWN = 0
    DISCONNECTED = 1
    CONNECTED = 2
    LOGGED_IN = 3
    LOGGED_OUT = 4


def fprint(encoded_msg):
    return encoded_msg.replace(b"\x01", b"|")


class FixEngine:
    """Enables interfacing with exchanges using the FIX (Financial Information eXchange) protocol.
    This class shall implement common logic for connection management and fulfill relevant functions from PyexAPI.

    Ideally, subclasses should not need to import simplefix, insulating them from implementation logic within.
    Note that simplefix automatically populates fields 9 (message length) and 10 (checksum)."""

    logger = logging.getLogger()
    read_timeout = 30
    write_timeout = 10
    read_buffer = 4096

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

        self.lock = asyncio.Lock()
        self.caller_loop = asyncio.get_event_loop()
        self.session_loop = None
        self.last_msg_sent = None
        self.logging_out = False

        self.write_queue = queue.Queue()
        self.application_messages = queue.Queue()

    async def _read_message(self):
        """Reads the next message from the server"""
        await self.lock.acquire()
        try:
            message = None
            # logging.debug("reading")
            buf = await self.reader.read(self.read_buffer)
            if not buf:
                raise ConnectionError
            self.parser.append_buffer(buf)
            message = self.parser.get_message()
            if message is None:
                return
            logging.debug(f"client received message {message}")
            assert isinstance(message, simplefix.FixMessage)

            # Handle session messages, queue application messages.
            if not self._handle_session_message(message):
                self.application_messages.put(message)
            # logging.debug(f"receive queue has {self.application_messages.qsize()} messages")

        except asyncio.CancelledError:
            logging.error("client read timed out")
            assert False
        finally:
            self.lock.release()
            pass

    def _handle_session_message(self, message: simplefix.FixMessage) -> bool:
        assert isinstance(message, simplefix.FixMessage)
        is_session_message = False

        if message.get(35) == b'A':  # logon response
            is_session_message = True
            self.connection_state = FixConnectionState.LOGGED_IN
        elif message.get(35) == b'1':  # send heartbeat in response to test request
            is_session_message = True
            m = self.create_message('0')
            m.append_pair(112, message.get(112))
            self.write(m)

        if message.get(141) == b'Y':  # handle request to reset sequence number
            logging.debug("resetting sequence number to 1")
            self.sequenceNum = 1

        return is_session_message

    async def _write_message(self, message: simplefix.FixMessage):
        """Sends a message to the server"""
        await self.lock.acquire()
        try:
            # logging.debug(f"client sending message {message}")
            self._append_sequence_number(message)
            self.writer.write(message.encode())
            logging.debug(f"client sending message {fprint(message.encode())}")
            await self.writer.drain()
            self.last_msg_sent = datetime.now()
        finally:
            self.lock.release()
            pass

    def write(self, message: simplefix.FixMessage):
        """Queues a message for submission"""
        self.write_queue.put(message)
        pass

    async def _wait_for_response(self, message_type: str) -> simplefix.FixMessage:
        assert isinstance(message_type, str)
        assert len(message_type) == 1

        while True:
            if not self.application_messages.empty():
                message = self.application_messages.get()
                assert isinstance(message, simplefix.FixMessage)
                if message.get(35) == message_type.encode('UTF-8'):
                    return message

    def wait_for_response(self, message_type: str) -> simplefix.FixMessage:
        logging.debug(f"waiting for 35={message_type} response")
        message = self.caller_loop.run_until_complete(self._wait_for_response(message_type))
        return message

    def create_message(self, message_type: str) -> simplefix.FixMessage:
        """Boilerplates a new message which the caller may populate as desired."""
        assert isinstance(message_type, str)
        assert len(message_type) == 1

        m = simplefix.FixMessage()
        m.append_pair(8, self.fix_version)
        m.append_pair(35, message_type)
        m.append_pair(49, self.senderCompId, header=True)
        m.append_pair(56, self.targetCompId, header=True)
        m.append_utc_timestamp(52, header=True)
        return m

    def logon(self):
        self.logging_out = False
        self.session_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        thread_name = f"FIX-{self.senderCompId}"
        session_thread = threading.Thread(target=self.run_session, daemon=True, name=thread_name)
        session_thread.start()

        m = self.create_message('A')
        m.append_pair(98, '0')
        m.append_pair(108, self.heartbeat_interval)
        m.append_pair(141, 'Y')
        m.append_pair(553, self.username)
        m.append_pair(554, self.password)
        self.write(m)

    def logout(self):
        self.logging_out = True
        # Send a logout message
        m = self.create_message('5')
        try:
            self.write_queue.put(m)
            self.last_msg_sent = None  # Prevent heartbeat during logout
            while not self.write_queue.empty():
                logging.debug("waiting to logout")
                time.sleep(1)
        except ConnectionError:
            pass
        finally:
            self.connection_state = FixConnectionState.LOGGED_OUT
        self.logging_out = False

    def run_session(self):
        self.session_loop.run_until_complete(self._session_proc())

    async def _session_proc(self):
        (address, port) = tuple(self.endpoint.split(':'))
        self.reader, self.writer = await asyncio.open_connection(address, port, loop=self.session_loop)
        self.connection_state = FixConnectionState.CONNECTED

        while self.connection_state != FixConnectionState.LOGGED_OUT:
            if not self.write_queue.empty():
                await self._write_message(self.write_queue.get())
            if not self.logging_out:
                await self._read_message()
                await self._heartbeat()

        logging.debug("exiting _session_proc")

    async def _heartbeat(self):
        assert self.heartbeat_interval > 0
        # logging.debug("checking for need to heartbeat")

        # Either we haven't attempted logon or we're logging out
        if not self.last_msg_sent:
            return

        if datetime.now() - self.last_msg_sent > timedelta(seconds=self.heartbeat_interval):
            try:
                m = self.create_message('0')
                await self._write_message(m)
            except ConnectionError as ex:
                logging.warning(f"Unable to send heartbeat: {ex}")
        # else:
        #     logging.debug(f"{datetime.now() - self.last_msg_sent} since last message sent; no need to heartbeat")

    def _append_sequence_number(self, m: simplefix.FixMessage):
        assert isinstance(m, simplefix.FixMessage)
        self.sequenceNum += 1
        m.append_pair(34, self.sequenceNum, header=True)
