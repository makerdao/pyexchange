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
from fxpmath import Fxp

MIN_TICK = -887272
MAX_TICK = 887272
MIN_SQRT_RATIO = Fxp(4295128739)
MAX_SQRT_RATIO = Fxp(1461446703485210103287273052203988822378723970342)
# TODO: figure out why this doesn't work
# MAX_UINT256 = Fxp('0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', signed=False, n_word=256)
MAX_UINT256 = Fxp(115792089237316195423570985008687907853269984665640564039457584007913129639935)
NEGATIVE_ONE = Fxp(-1)
ZERO = Fxp(0)
ONE = Fxp(1)
Q96 = Fxp(2 ** 96)
Q192 = Fxp(Q96 ** 2)

class FEES(Enum):
    LOW = 500
    MEDIUM = 3000
    HIGH = 10000


# default tick sizes by fee amount
class TICK_SPACING(Enum):
    LOW = 10
    MEDIUM = 60
    HIGH = 200