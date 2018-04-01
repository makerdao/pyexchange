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

import requests

from pyexchange.model import Candle
from pymaker.numeric import Wad
from pymaker.util import http_response_summary


class GDAXApi:
    """GDAX API interface.

    Developed according to the following manual:
    <https://docs.gdax.com/>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.timeout = timeout

    def candles(self, pair: str, granularity: int) -> List[Candle]:
        assert(isinstance(pair, str))
        assert(isinstance(granularity, int))

        assert(granularity in (60, 300, 900, 3600, 21600, 86400))

        result = requests.get(f"{self.api_server}/products/{pair}/candles?"
                              f"granularity={granularity}", timeout=self.timeout)

        if not result.ok:
            raise Exception(f"GDAX API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"GDAX API invalid JSON response: {http_response_summary(result)}")

        if 'message' in data:
            raise Exception(f"GDAX API negative response: {http_response_summary(result)}")

        return list(map(lambda item: Candle(timestamp=int(item[0]),
                                            open=Wad.from_number(item[3]),
                                            close=Wad.from_number(item[4]),
                                            high=Wad.from_number(item[2]),
                                            low=Wad.from_number(item[1]),
                                            volume=Wad.from_number(item[5])), data))
