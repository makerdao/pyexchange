# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus
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
from typing import List

import dateutil.parser
import requests

from pyexchange.model import Candle
from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class UpbitApi:
    """Upbit API interface.

    Developed according to the following manual:
    <https://steemit.com/kr/@segyepark/api>.
    """

    logger = logging.getLogger()

    def __init__(self, timeout: float):
        assert(isinstance(timeout, float))
        self.timeout = timeout

    def candles(self, pair: str, granularity: int, count: int) -> List[Candle]:
        assert(isinstance(pair, str))
        assert(isinstance(granularity, int))

        assert(granularity in (1, 3, 5, 10 , 15, 30, 60, 240))

        response = requests.get(f"https://crix-api-endpoint.upbit.com/v1/crix/candles/minutes/{granularity}?"
                                f"code=CRIX.UPBIT.{pair}&count={count}", timeout=self.timeout)

        if not response.ok:
            raise Exception(f"Upbit API invalid HTTP response: {http_response_summary(response)}")

        return list(map(lambda item: Candle(timestamp=int(dateutil.parser.parse(item['candleDateTime']).timestamp()),
                                            open=Wad.from_number(item['openingPrice']),
                                            close=Wad.from_number(item['tradePrice']),
                                            high=Wad.from_number(item['highPrice']),
                                            low=Wad.from_number(item['lowPrice']),
                                            volume=Wad.from_number(item['candleAccTradeVolume'])), response.json()))
