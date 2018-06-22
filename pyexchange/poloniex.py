# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus, bargst
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

import logging
from pprint import pformat
from typing import List
from datetime import datetime, timezone

import requests

from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class Trade:
    def __init__(self,
                 trade_id: id,
                 timestamp: float,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int))
        assert(isinstance(timestamp, float))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))


class PoloniexApi:
    """Poloniex API interface.

    Developed according to the following manual:
    <https://poloniex.com/support/api/>
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.timeout = timeout

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        assert(page_number == 1)

        result = self._http_get("/public", f"command=returnTradeHistory&currencyPair={pair}")
        return list(map(lambda item: Trade(trade_id=int(item['globalTradeID']),
                                           timestamp=self._date_to_timestamp(item['date']),
                                           is_sell=item['type'] == 'sell',
                                           price=Wad.from_number(item['rate']),
                                           amount=Wad.from_number(item['amount'])), result))

    def _date_to_timestamp(self, date: str) -> float:
        dt = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=timezone.utc).timestamp()

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"Poloniex API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Poloniex API invalid JSON response: {http_response_summary(result)}")

        return data

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         timeout=self.timeout))
