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
import simplefix
import threading


class MockFixServer:
    def __init__(self):
        self.receivedData = False
        self.loop = asyncio.new_event_loop()
        self.parser = simplefix.FixParser()

    def start(self):
        coro = asyncio.start_server(self.handle_data, '127.0.0.1', 1752, loop=self.loop)
        self.loop.run_until_complete(coro)

    def run(self):
        print(f"server running on thread {threading.current_thread()}")
        self.loop.run_forever()
        print("server stopped running")

    @asyncio.coroutine
    async def handle_data_old(self, reader, writer):
        request = None
        while not self.receivedData:
            self.receivedData = True
            request = (await reader.read(255)).decode('utf8')
            print(f"server received {request}")
            # TODO: Call a method which responds to the request based on message type (tag 35)
            response = request
            writer.write(response.encode('utf8'))
            print("server sent response")
            await asyncio.sleep(1)
        writer.close()

    @asyncio.coroutine
    async def handle_data(self, reader, writer):
        while True:
            message = await self._read_message(reader)
            self.handle_message(message, writer)
            self.receivedData = True
            writer.write(f"response message".encode('utf-8'))
            print("server sent response")
            break
        writer.close()
        print(f"server exiting handle_data on thread {threading.current_thread()}")

    async def _read_message(self, reader):
        """Reads the next message from the server"""
        message = None
        while message is None:
            buf = await reader.read(255)
            self.parser.append_buffer(buf)
            message = self.parser.get_message()
        print(f"server received message {message}")
        return message

    def handle_message(self, message, writer):
        print("server handle_message called")
        message_type = message.get(35)
        if message_type == b'A':
            # Echo back the logon message
            writer.write(message.encode())
        else:
            raise NotImplementedError(f"message_type={message_type} not supported")
