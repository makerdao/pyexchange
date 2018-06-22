import asyncio
import json
import logging
import websockets

from functools import partial

class PyexAPI:
    """
    Define a common abstract API for exchanges
    """

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
        raise NotImplementedError()

    def cancel_order(self, order_id):
        raise NotImplementedError()

    def get_trades(self, pair, page_number):
        raise NotImplementedError()

    def get_all_trades(self, pair, page_number):
        raise NotImplementedError()


class AsyncAPI:
    """
    Wrap PyexAPI calls into Asyncio coroutines using a call to
        asyncio.loop.run_in_executor()
    """

    def __init__(self, loop, executor, api):
        self.loop = loop
        self.executor = executor
        self.api = api

    async def _call(self, function, *args, **kwargs):
        func_call = partial(function, *args, **kwargs)
        return await self.loop.run_in_executor(self.executor, func_call)

    async def ticker(self, *args, **kwargs):
        return await self._call(self.api.ticker, *args, **kwargs)

    async def get_markets(self, *args, **kwargs):
        return await self._call(self.api.get_markets, *args, **kwargs)

    async def get_pair(self, *args, **kwargs):
        return await self._call(self.api.get_pair, *args, **kwargs)

    async def get_balances(self, *args, **kwargs):
        return await self._call(self.api.get_balances, *args, **kwargs)

    async def get_orders(self, *args, **kwargs):
        return await self._call(self.api.get_orders, *args, **kwargs)

    async def place_order(self, *args, **kwargs):
        return await self._call(self.api.place_order, *args, **kwargs)

    async def cancel_order(self, *args, **kwargs):
        return await self._call(self.api.cancel_order, *args, **kwargs)

    async def get_trades(self, *args, **kwargs):
        return await self._call(self.api.get_trades, *args, **kwargs)

    async def get_all_trades(self, *args, **kwargs):
        return await self._call(self.api.get_all_trades, *args, **kwargs)


class StreamAPI:

    logger = logging.getLogger()

    def __init__(self, loop, ws_url, timeout=5):
        self.loop = loop
        self.ws_url = ws_url
        self.timeout = timeout
        self.msg_q = asyncio.Queue()

        self.loop.create_task(self.main())

    async def subscribe(self, websocket):
        raise NotImplementedError()

    async def get(self):
        return await self.msg_q.get()

    async def main(self):
        while True:
            try:
                await self.work()
            except:
                self.logger.exception(f'Exception occured, sleeping {self.timeout}s before ws reconnect')
                await asyncio.sleep(self.timeout)

    async def work(self):
        async with websockets.connect(self.ws_url) as websocket:
            await self.subscribe(websocket)
            while True:
                try:
                    recv = await asyncio.wait_for(websocket.recv(), timeout=self.timeout)
                    msg = json.loads(recv)
                    self.logger.debug(f'Received msg={msg}')
                    await self.msg_q.put(msg)
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.timeout)
                    except asyncio.TimeoutError:
                        # No response to ping, disconnect.
                        break
