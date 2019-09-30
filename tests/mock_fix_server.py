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
import os
import simplefix
import threading

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


class MockFixServer:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.parser = simplefix.FixParser()
        self.heartbeat_count = 0
        self.server = None

    def run(self):
        print("server calling asyncio.start_server")
        coro = asyncio.start_server(self.handle_data, '127.0.0.1', 1752, loop=self.loop)
        self.server = self.loop.run_until_complete(coro)
        print("server __init__ returning")

        print(f"server running on thread {threading.current_thread()} in process {os.getpid()}")
        self.loop.run_forever()

    def run_in_another_process(self):
        # FIXME: executor.submit unexpectedly blocks, so this is useless
        with ProcessPoolExecutor(max_workers=2) as executor:
            executor.submit(self.run)

    def run_in_another_thread(self):
        # FIXME: loop.run_in_executor blocks, so this is useless
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.loop.run_in_executor(executor, self.run)

    async def handle_data(self, reader, writer):
        print(f"server entering handle_data on thread {threading.current_thread()}")
        # while True:
        message = await self._read_message(reader)
        await self.handle_message(message, writer)
        # await asyncio.sleep(1)
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

    async def _write_message(self, message: simplefix.FixMessage, writer):
        """Sends a message to the server"""
        print(f"server sending message {message}")
        writer.write(message.encode())
        await writer.drain()
        print("server drained writer")

    async def handle_message(self, message, writer):
        message_type = message.get(35)
        if message_type == b'A':
            # Echo back the logon message
            await self._write_message(message, writer)
        elif message_type == b'0':
            self.heartbeat_count += 1
        else:
            raise NotImplementedError(f"message_type={message_type} not supported")


if __name__ == "__main__":
    server = MockFixServer()
    server.run()
