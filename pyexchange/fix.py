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
import ssl

from datetime import datetime, timedelta
from enum import Enum
from typing import List


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

    Note that simplefix automatically populates fields 9 (message length) and 10 (checksum)."""

    logger = logging.getLogger()
    read_timeout = 30
    write_timeout = 10
    read_buffer = 128

    def __init__(self, endpoint: str, sender_comp_id: str, target_comp_id: str, username: str, password: str,
                 certs: dict, fix_version="FIX.4.4", heartbeat_interval=3):
        assert isinstance(endpoint, str)
        assert isinstance(sender_comp_id, str)
        assert isinstance(target_comp_id, str)
        assert isinstance(username, str)
        assert isinstance(password, str)
        assert(isinstance(certs, dict) or (certs is None))
        self.endpoint = endpoint
        self.senderCompId = sender_comp_id
        self.targetCompId = target_comp_id
        self.username = username
        self.password = password
        self.certs = certs
        self.fix_version = fix_version
        self.heartbeat_interval = heartbeat_interval
        self.sequenceNum = 0
        self.connection_state = FixConnectionState.DISCONNECTED

        self.reader = None
        self.writer = None
        self.parser = simplefix.FixParser()

        # This lock probably isn't needed because `reader.read` blocks.
        self.lock = asyncio.Lock()
        self.caller_loop = asyncio.get_event_loop()
        self.session_loop = None
        self.last_msg_sent = None
        self.logging_out = False

        self.write_queue = queue.Queue()
        self.application_messages = queue.Queue()

    async def _read_message(self):
        """Reads the next message from the server"""
        try:
            message = None
            while message is None:
                buf = await self.reader.read(self.read_buffer)
                if not buf:
                    break
                self.parser.append_buffer(buf)
                message = self.parser.get_message()

            # Handle None responses from order mass status requests
            if message is None:
                return

            logging.debug(f"client received message {message}")
            assert isinstance(message, simplefix.FixMessage)

            # Handle session messages, queue application messages.
            if not self._handle_session_message(message):
                self.application_messages.put(message)

        except asyncio.CancelledError:
            logging.error("client read timed out")
            assert False
        finally:
            await asyncio.sleep(0.3)
            pass

    def _handle_session_message(self, message: simplefix.FixMessage) -> bool:
        assert isinstance(message, simplefix.FixMessage)
        is_session_message = False

        if message.get(simplefix.TAG_MSGTYPE) == simplefix.MSGTYPE_LOGON:
            is_session_message = True
            self.connection_state = FixConnectionState.LOGGED_IN
        elif message.get(simplefix.TAG_MSGTYPE) == simplefix.MSGTYPE_TEST_REQUEST:
            is_session_message = True
            m = self.create_message(simplefix.MSGTYPE_HEARTBEAT)
            m.append_pair(simplefix.TAG_TESTREQID, message.get(simplefix.TAG_TESTREQID))
            self.write(m)

        if message.get(simplefix.TAG_RESETSEQNUMFLAG) == simplefix.RESETSEQNUMFLAG_YES:
            logging.debug("resetting sequence number to 1")
            self.sequenceNum = 1

        return is_session_message

    async def _write_message(self, message: simplefix.FixMessage):
        """Sends a message to the server"""
        await self.lock.acquire()
        # This lock is needed for `logout` method, which writes synchronously rather than through write_queue
        try:
            self._append_sequence_number(message)
            self.writer.write(message.encode())
            logging.debug(f"client sending message {fprint(message.encode())}")
            await self.writer.drain()
            self.last_msg_sent = datetime.now()
        finally:
            self.lock.release()

    def write(self, message: simplefix.FixMessage):
        """Queues a message for submission"""
        self.write_queue.put(message)
        pass

    async def _wait_for_response(self, message_type: str) -> simplefix.FixMessage:
        assert isinstance(message_type, str)
        assert len(message_type) == 1

        reject_message_types = [simplefix.MSGTYPE_BUSINESS_MESSAGE_REJECT, simplefix.MSGTYPE_ORDER_CANCEL_REJECT]

        while True:
            if not self.application_messages.empty():
                message = self.application_messages.get()
                assert isinstance(message, simplefix.FixMessage)

                # handle message rejection
                if message.get(simplefix.TAG_MSGTYPE) in reject_message_types:
                    if message.get(102) is not None:
                        logging.error(f"Order cancellation rejected due to {message.get(58).decode('utf-8')}, tag_102 code: {message.get(102).decode('utf-8')}")
                    return message

                if message.get(simplefix.TAG_MSGTYPE) == message_type.encode('UTF-8'):
                    if message.get(103) is not None:
                        logging.error(f"Order placement rejected due to {message.get(58).decode('utf-8')}, tag_103 code: {message.get(103).decode('utf-8')}")
                    return message
            await asyncio.sleep(0.3)

    def wait_for_response(self, message_type: str) -> simplefix.FixMessage:
        logging.debug(f"waiting for 35={message_type} response")
        message = self.caller_loop.run_until_complete(self._wait_for_response(message_type))
        return message

    # Assumes always waiting for message type 8
    async def _wait_for_get_orders_response(self) -> List[simplefix.FixMessage]:
        order_messages = []

        reject_message_types = [simplefix.MSGTYPE_BUSINESS_MESSAGE_REJECT, simplefix.MSGTYPE_ORDER_CANCEL_REJECT]

        while True:
            if not self.application_messages.empty():
                message = self.application_messages.get()
                assert isinstance(message, simplefix.FixMessage)

                # handle message rejection
                if message.get(simplefix.TAG_MSGTYPE) in reject_message_types:
                    return order_messages

                # for retrieving order information, check if response type is 8, that 912 = y for last message
                if message.get(simplefix.TAG_MSGTYPE) == simplefix.MSGTYPE_EXECUTION_REPORT:
                    if message.get(912) == 'Y'.encode('utf-8'):
                        order_messages.append(message)
                        return order_messages
                    else:
                        order_messages.append(message)

            await asyncio.sleep(0.3)

    def wait_for_get_orders_response(self) -> List[simplefix.FixMessage]:
        logging.debug(f"waiting for 35={8} Order Mass Status Request response")
        messages = self.caller_loop.run_until_complete(self._wait_for_get_orders_response())
        return messages

    def create_message(self, message_type: bytes) -> simplefix.FixMessage:
        """Boilerplates a new message which the caller may populate as desired."""
        assert isinstance(message_type, bytes)
        assert 1 <= len(message_type) <= 2

        m = simplefix.FixMessage()
        m.append_pair(simplefix.TAG_BEGINSTRING, self.fix_version)
        m.append_pair(simplefix.TAG_MSGTYPE, message_type)
        m.append_pair(simplefix.TAG_SENDER_COMPID, self.senderCompId, header=True)
        m.append_pair(simplefix.TAG_TARGET_COMPID, self.targetCompId, header=True)
        m.append_utc_timestamp(simplefix.TAG_SENDING_TIME, header=True)
        return m

    def logon(self):
        self.logging_out = False
        self.session_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        thread_name = f"FIX-{self.senderCompId}"
        session_thread = threading.Thread(target=self._run_session, daemon=True, name=thread_name)
        session_thread.start()

        m = self.create_message(simplefix.MSGTYPE_LOGON)
        m.append_pair(simplefix.TAG_ENCRYPTMETHOD, '0')
        m.append_pair(simplefix.TAG_HEARTBTINT, self.heartbeat_interval)
        m.append_pair(simplefix.TAG_RESETSEQNUMFLAG, 'Y')
        m.append_pair(553, self.username)
        m.append_pair(554, self.password)
        self.write(m)

    def logout(self):
        self.logging_out = True
        # Send a logout message
        m = self.create_message(simplefix.MSGTYPE_LOGOUT)
        try:
            self.caller_loop.run_until_complete(self._write_message(m))
            self.last_msg_sent = None  # Prevent heartbeat during logout
            while not self.write_queue.empty():
                logging.debug("waiting to logout")
                time.sleep(1)
        except ConnectionError:
            pass
        finally:
            self.connection_state = FixConnectionState.LOGGED_OUT
        self.logging_out = False

    def _run_session(self):
        self.session_loop.run_until_complete(self._session_proc())

    async def _session_proc(self):
        (address, port) = tuple(self.endpoint.split(':'))

        if self.certs is not None:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            self.ssl_context.load_cert_chain(certfile=self.certs['client_cert'], keyfile=self.certs['client_key'])
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            self.reader, self.writer = await asyncio.open_connection(address, port, loop=self.session_loop, ssl=self.ssl_context)
        else:
            self.reader, self.writer = await asyncio.open_connection(address, port, loop=self.session_loop)

        self.connection_state = FixConnectionState.CONNECTED

        while self.connection_state != FixConnectionState.LOGGED_OUT:
            if not self.write_queue.empty():
                await self._write_message(self.write_queue.get())
            if not self.logging_out:
                await self._read_message()
                await self._heartbeat()

    async def _heartbeat(self):
        assert self.heartbeat_interval > 0

        # Either we haven't attempted logon or we're logging out
        if not self.last_msg_sent:
            return

        if datetime.now() - self.last_msg_sent > timedelta(seconds=self.heartbeat_interval):
            try:
                m = self.create_message(simplefix.MSGTYPE_HEARTBEAT)
                await self._write_message(m)
            except ConnectionError as ex:
                logging.warning(f"Unable to send heartbeat: {ex}")

    def _append_sequence_number(self, m: simplefix.FixMessage):
        assert isinstance(m, simplefix.FixMessage)
        self.sequenceNum += 1
        m.append_pair(34, self.sequenceNum, header=True)
