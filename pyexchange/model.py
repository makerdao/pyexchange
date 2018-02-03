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

from pprint import pformat

from pymaker import Wad


class Candle:
    def __init__(self, timestamp: int, open: Wad, close: Wad, high: Wad, low: Wad, volume: Wad):
        assert(isinstance(timestamp, int))
        assert(isinstance(open, Wad))
        assert(isinstance(close, Wad))
        assert(isinstance(high, Wad))
        assert(isinstance(low, Wad))
        assert(isinstance(volume, Wad))

        self.timestamp = timestamp
        self.open = open
        self.close = close
        self.high = high
        self.low = low
        self.volume = volume

    def __repr__(self):
        return pformat(vars(self))
