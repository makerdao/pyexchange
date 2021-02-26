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

from pyexchange.model import Order
from pymaker.numeric import Wad


class FixConnectionState(Enum):
    UNKNOWN = 0
    DISCONNECTED = 1
    CONNECTED = 2
    LOGGED_IN = 3
    LOGGED_OUT = 4


def fprint(encoded_msg):
    return encoded_msg.replace(b"\x01", b"|")


# TODO: add callback based abstraction that can be subclassed for various socket listeners
# TODO: move wait for listerners to ErisxFix
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

        # clientId: Queue
        self.order_book = {}

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

            logging.info(f"client received message {message}")
            assert isinstance(message, simplefix.FixMessage)

            # Handle session messages, queue application messages.
            if not self._handle_session_message(message):
                await self.lock.acquire()
                self._handle_application_message(message)
                self.lock.release()

        except asyncio.CancelledError:
            logging.error("client read timed out")
            assert False
        finally:
            await asyncio.sleep(0.3)
            pass

    def _handle_application_message(self, message: simplefix.FixMessage):
        """
            If application message is an order processing message,
            add it to the order_book keyed by the messages client_order_id.

            Otherwise, add marketdata messages to application_messages queue.
        """
        assert isinstance(message, simplefix.FixMessage)

        # handle ORDER MASS STATUS REQUEST messages
        if message.get(b'584') != None:
            self.application_messages.put(message)
            return

        order_processing_types = [simplefix.MSGTYPE_EXECUTION_REPORT, simplefix.MSGTYPE_ORDER_CANCEL_REJECT]

        # handle order processing messages
        if message.get(simplefix.TAG_MSGTYPE) in order_processing_types:

            # ensure the correct client id is used, depending on order execution type
            use_origclordid_types = [simplefix.EXECTYPE_CANCELED, simplefix.EXECTYPE_REPLACE, simplefix.EXECTYPE_PENDING_CANCEL, simplefix.EXECTYPE_PENDING_REPLACE]

            if message.get(simplefix.TAG_EXECTYPE) in use_origclordid_types:
                client_order_id = f"{message.get(simplefix.TAG_ORIGCLORDID).decode('utf-8')}"
            else:
                client_order_id = f"{message.get(simplefix.TAG_CLORDID).decode('utf-8')}"

            if client_order_id not in self.order_book:
                self.order_book[client_order_id] = queue.Queue()

            self.order_book[client_order_id].put(message)

        # keep marketdata messages in application queue
        else:
            self.application_messages.put(message)

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
            logging.info("resetting sequence number to 1")
            self.sequenceNum = 1

        return is_session_message

    async def _write_message(self, message: simplefix.FixMessage):
        """Sends a message to the server"""
        await self.lock.acquire()
        # This lock is needed for `logout` method, which writes synchronously rather than through write_queue
        try:
            self._append_sequence_number(message)
            self.writer.write(message.encode())
            logging.info(f"client sending message {fprint(message.encode())}")
            await self.writer.drain()
            self.last_msg_sent = datetime.now()
        finally:
            self.lock.release()

    def write(self, message: simplefix.FixMessage):
        """Queues a message for submission"""
        self.write_queue.put(message)
        pass

    async def _delete_order(self, client_order_id: str):
        assert (isinstance(client_order_id, str))

        await self.lock.acquire()
        try:
            del self.order_book[client_order_id]
        except Exception as e:
            self.logger.error(f"Unable to delete order due to {e}")
        finally:
            self.lock.release()

    def _get_client_id(self, order_id: str) -> str:
        """ Retrieve the client_id from an order_id structured as exchange_id|client_id """
        assert isinstance(order_id, str)

        return order_id.split('|')[1]

    async def _sync_orders(self, orders: List[Order]) -> List[dict]:
        """
            Iterate through clients list of orders and update according to exchange state.

            If an order has been canceled or completely filled, delete the entry in the order book.

            Finally, return a list of dictionaries: {order_id: filled_amount}.
            This enables us to keep amounts in sync in the event of partial fills.
        """
        assert isinstance(orders, List)

        cancel_message_types = [simplefix.EXECTYPE_CANCELED, simplefix.EXECTYPE_EXPIRED]
        open_orders = []

        for order in orders:
            client_order_id = self._get_client_id(order.order_id)
            order_status_dict = {}

            if client_order_id in self.order_book:
                while not self.order_book[client_order_id].empty():
                    exchange_order_state = self.order_book[client_order_id].get()
                    order_id = f"{exchange_order_state.get(simplefix.TAG_ORDERID)}|{exchange_order_state.get(simplefix.TAG_CLORDID)}"

                    # check for cancellations
                    if exchange_order_state.get(simplefix.TAG_EXECTYPE) in cancel_message_types:
                        await self._delete_order(client_order_id)
                        break
                    # check for unsolicited cancellations (can be received for non exectype messages)
                    elif exchange_order_state.get(b'5001') is not None:
                        self.logger.warning(f"Unsolicited Cancellation for order: {order_id}")
                        await self._delete_order(client_order_id)
                        break

                    # check for fills
                    if exchange_order_state.get(simplefix.TAG_EXECTYPE) == b'F':
                        if exchange_order_state.get(simplefix.TAG_ORDSTATUS) == simplefix.ORDSTATUS_FILLED:
                            self.logger.info(f"Order: {order_id} filled with amount {exchange_order_state.get(simplefix.TAG_CUMQTY).decode('utf-8')} at price of {exchange_order_state.get(simplefix.TAG_PRICE).decode('utf-8')}")

                            await self._delete_order(client_order_id)
                            break
                        elif exchange_order_state.get(simplefix.TAG_ORDSTATUS) == simplefix.ORDSTATUS_PARTIALLY_FILLED:
                            self.logger.info(f"Order: {order_id} partially filled with amount {exchange_order_state.get(simplefix.TAG_CUMQTY).decode('utf-8')}  at price of {exchange_order_state.get(simplefix.TAG_PRICE).decode('utf-8')}")

                            order_status_dict[order.order_id] = Wad.from_number(float(exchange_order_state.get(simplefix.TAG_CUMQTY).decode('utf-8')))
                            if self.order_book[client_order_id].empty():
                                open_orders.append(order_status_dict)

            # keep open orders in state
            not_in_open_orders = all(map(lambda open_order: order.order_id not in open_order.keys(), open_orders))
            if client_order_id in self.order_book and not_in_open_orders:
                order_status_dict[order.order_id] = Wad.from_number(0)
                open_orders.append(order_status_dict)

        return open_orders

    def sync_orders(self, orders: List[Order]) -> List[dict]:
        logging.info(f"Synchronizing Order state")
        orders = self.caller_loop.run_until_complete(self._sync_orders(orders))
        return orders

    async def _wait_for_order_processing_response(self, message_type: str, client_order_id: str) -> simplefix.FixMessage:
        assert isinstance(message_type, str)
        assert isinstance(client_order_id, str)

        reject_message_types = [simplefix.MSGTYPE_BUSINESS_MESSAGE_REJECT, simplefix.MSGTYPE_ORDER_CANCEL_REJECT]

        while True:
            if client_order_id in self.order_book:
                if not self.order_book[client_order_id].empty():
                    message = self.order_book[client_order_id].get()
                    assert isinstance(message, simplefix.FixMessage)

                    # handle message rejection
                    if message.get(simplefix.TAG_MSGTYPE) in reject_message_types:
                        if message.get(simplefix.TAG_CXLREJREASON) is not None:
                            logging.error(f"Order cancellation rejected due to {message.get(58).decode('utf-8')}, tag_102 code: {message.get(102).decode('utf-8')}")
                        if message.get(simplefix.TAG_ORDERREJREASON) is not None:
                            logging.error(f"Order placement rejected due to {message.get(58).decode('utf-8')}, tag_103 code: {message.get(103).decode('utf-8')}")
                        return message

                    if message.get(simplefix.TAG_MSGTYPE) == message_type.encode('UTF-8'):
                        # Remove orders that have been cancelled from the order book
                        if message.get(simplefix.TAG_EXECTYPE) == simplefix.EXECTYPE_CANCELED:
                            await self._delete_order(client_order_id)
                        # Remove orders that recieve an UnsolicitedCancel response
                        if message.get(b'5001') is not None:
                            await self._delete_order(client_order_id)
                        return message
            await asyncio.sleep(0.3)

    def wait_for_order_processing_response(self, message_type: str, client_order_id: str) -> simplefix.FixMessage:
        logging.info(f"waiting for 35={message_type} response")
        message = self.caller_loop.run_until_complete(self._wait_for_order_processing_response(message_type, client_order_id))
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

    async def _wait_for_response(self, message_type: str) -> simplefix.FixMessage:
        assert isinstance(message_type, str)

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
        logging.info(f"waiting for 35={message_type} response")
        message = self.caller_loop.run_until_complete(self._wait_for_response(message_type))
        return message

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
                logging.info("waiting to logout")
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

        try:
            if self.certs is not None:
                self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                self.ssl_context.load_cert_chain(certfile=self.certs['client_cert'], keyfile=self.certs['client_key'])
                self.ssl_context.check_hostname = False
                self.ssl_context.verify_mode = ssl.CERT_NONE
                self.reader, self.writer = await asyncio.open_connection(address, port, loop=self.session_loop, ssl=self.ssl_context)
            else:
                self.reader, self.writer = await asyncio.open_connection(address, port, loop=self.session_loop)

            self.connection_state = FixConnectionState.CONNECTED
        except Exception as e:
            logging.error(f"Unable to connect due to {e}")

        while self.connection_state != FixConnectionState.LOGGED_OUT:
            if not self.reader:
                logging.warning("Socket reader was closed; exiting")
                return
            if not self.writer:
                logging.warning("Socket writer was closed; exiting")
                return
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
