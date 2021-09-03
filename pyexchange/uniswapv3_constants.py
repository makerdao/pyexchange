# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2021 MikeHathaway
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

from enum import Enum

MAX_FEE = 10 ** 6
MIN_TICK = -887272
MAX_TICK = 887272
MIN_SQRT_RATIO = 4295128739
MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935
MAX_UINT160 = (2 ** 160) - 1
MAX_UINT128 = (2 ** 128) - 1
NEGATIVE_ONE = -1
ZERO = 0
ONE = 1
Q96 = 2 ** 96
Q192 = Q96 ** 2


# default fee amounts in hundreths of basis points
class FEES(Enum):
    LOW = 500
    MEDIUM = 3000
    HIGH = 10000


# default tick sizes by fee amount
class TICK_SPACING(Enum):
    LOW = 10
    MEDIUM = 60
    HIGH = 200


class TRADE_TYPE(Enum):
    EXACT_OUTPUT = "exactOutput"
    EXACT_OUTPUT_SINGLE = "exactOutputSingle"
    EXACT_INPUT = "exactInput"
    EXACT_INPUT_SINGLE = "exactInputSingle"
