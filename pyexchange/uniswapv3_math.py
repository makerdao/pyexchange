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

import math

from pymaker.numeric import Wad
from fxpmath import Fxp

## Used by uniswap-v3-sdk
# https://github.com/GoogleChromeLabs/jsbi
# find python bigint equivalent to jsbi

# TODO: use this library
# https://github.com/francof2a/fxpmath

## Fixed Point Numbers guides
# https://en.wikipedia.org/wiki/Q_(number_format)
# https://www.khanacademy.org/computing/computers-and-internet/xcae6f4a7ff015e7d:digital-information/xcae6f4a7ff015e7d:limitations-of-storing-numbers/a/number-limits-overflow-and-roundoff
# https://ethereum.stackexchange.com/questions/98685/computing-the-uniswap-v3-pair-price-from-q64-96-number
# https://stackoverflow.com/questions/60684695/how-to-handle-a-large-input-in-an-integer-square-root-method


# POWERS_OF_2 = [128, 64, 32, 16, 8, 4, 2, 1]
# # TODO: should this return a Fxp?
# def most_significant_bit(x: Fxp) -> int:
#     most_significant_bit = 0

#     for power, min of 

MIN_TICK = -887272
MAX_TICK = 887272
MIN_SQRT_RATIO = Fxp(4295128739)
MAX_SQRT_RATIO = Fxp(1461446703485210103287273052203988822378723970342)
MAX_UINT256 = Fxp('0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff')

# https://www.geeksforgeeks.org/find-significant-set-bit-number/
def most_significant_bit(x: Fxp) -> Fxp:
    """ returns the most significant bit for a given number"""
    k = int(math.log(x, 2))
    msb = 1 << k

    return Fxp(msb)

# TODO: check return type
def mul_shift(value: Fxp, multiply_by: string) -> Fxp:
    """ """
    assert (isinstance(value, Fxp))
    assert (isinstance(multiply_by, str))

    # signed right shift
    number = value * (Fxp(multiply_by)) >> Fxp(128)
    return Fxp(number)

# TODO: finish implementing
def getSqrtRatioAtTick(tick: Fxp) -> Fxp:
    assert (isinstance(tick, Fxp))

    abs_tick = tick * - 1 if tick < 0 else tick

    ratio = Fxp('0xfffcb933bd6fad37aa2d162d1a594001') if (abs_tick & Fxp('0x1')) != 0 else Fxp('0x100000000000000000000000000000000')

    if abs_tick & Fxp('0x2') != 0:
        ratio = mul_shift(ratio, '0xfff97272373d413259a46990580e213a')
    if abs_tick & Fxp('0x4') != 0:
        ratio = mul_shift(ratio, '0xfff2e50f5f656932ef12357cf3c7fdcc')
    if abs_tick & Fxp('0x8') != 0:
        ratio = mul_shift(ratio, '0xffe5caca7e10e4e61c3624eaa0941cd0')
    if abs_tick & Fxp('0x10') != 0:
        ratio = mul_shift(ratio, '0xffcb9843d60f6159c9db58835c926644')
    if abs_tick & Fxp('0x20') != 0:
        ratio = mul_shift(ratio, '0xff973b41fa98c081472e6896dfb254c0')
    if abs_tick & Fxp('0x40') != 0:
        ratio = mul_shift(ratio, '0xff2ea16466c96a3843ec78b326b52861')
    if abs_tick & Fxp('0x80') != 0:
        ratio = mul_shift(ratio, '0xfe5dee046a99a2a811c461f1969c3053')
    if abs_tick & Fxp('0x100') != 0:
        ratio = mul_shift(ratio, '0xfcbe86c7900a88aedcffc83b479aa3a4')
    if abs_tick & Fxp('0x200') != 0:
        ratio = mul_shift(ratio, '0xf987a7253ac413176f2b074cf7815e54')
    if abs_tick & Fxp('0x400') != 0:
        ratio = mul_shift(ratio, '0xf3392b0822b70005940c7a398e4b70f3')
    if abs_tick & Fxp('0x800') != 0:
        ratio = mul_shift(ratio, '0xe7159475a2c29b7443b29c7fa6e889d9')
    if abs_tick & Fxp('0x1000') != 0:
        ratio = mul_shift(ratio, '0xd097f3bdfd2022b8845ad8f792aa5825')
    if abs_tick & Fxp('0x2000') != 0:
        ratio = mul_shift(ratio, '0xa9f746462d870fdf8a65dc1f90e061e5')
    if abs_tick & Fxp('0x4000') != 0:
        ratio = mul_shift(ratio, '0x70d869a156d2a1b890bb3df62baf32f7')
    if abs_tick & Fxp('0x8000') != 0:
        ratio = mul_shift(ratio, '0x31be135f97d08fd981231505542fcfa6')
    if abs_tick & Fxp('0x10000') != 0:
        ratio = mul_shift(ratio, '0x9aa508b5b7a84e1c677de54f3e99bc9')
    if abs_tick & Fxp('0x20000') != 0:
        ratio = mul_shift(ratio, '0x5d6af8dedb81196699c329225ee604')
    if abs_tick & Fxp('0x40000') != 0:
        ratio = mul_shift(ratio, '0x2216e584f5fa1ea926041bedfe98')
    if abs_tick & Fxp('0x80000') != 0:
        ratio = mul_shift(ratio, '0x48a170391f7dc42444e8fa2')

    if tick > 0:
        ratio = MAX_UINT256 / ratio

    # convert back to Q64.96


# https://github.com/Uniswap/uniswap-v3-sdk/blob/c8e0d4c56e3b3ebd6446aba66523d20f2ea0fd9c/src/utils/tickMath.ts#L82
# TODO: add FXP Qm.n typing? Add signing?
# TODO: clean up Fxp instantiation / add constants -> add support for Fxp templates?
def getTickAtSqrtRatio(sqrtRatioX96: Fxp) -> int:
    """ return the tick for a given Q64.96 formatted ratio (64 bit word, 96 fractional bits) """
    assert (isinstance(sqrtRatioX96, Fxp))

    square_root_ratio_x128 = sqrtRatioX96 << Fxp(32)

    msb = most_significant_bit(square_root_ratio_x128)

    r = None
    if msb > Fxp(128):
        # signed right shift
        r = square_root_ratio_x128 >> (msb - Fxp(127))
    else:
        # left shift
        r = square_root_ratio_x128 << (Fxp(127) - msb)

    # TODO: figure out how to deal with sign... dealt with by Fxp internals?
    log_2 = (msb - Fxp(128)) << Fxp(64)

    for i in range(14):
        # signed right shift
        r = (r * r) >> Fxp(127)
        f = r >> Fxp(128)

        # leftshift bitwise OR
        log_2 = log_2 | f << Fxp(63 - i)

        # signed right shift
        r = r >> f

    log_sqrt10001 = (log_2 * Fxp(255738958999603826347141))

    tick_low = (log_sqrt10001 - Fxp(3402992956809132418596140100660247210)) >> Fxp(128)
    tick_high = (log_sqrt10001 + Fxp(291339464771989622907027621153398088495)) >> Fxp(128)

    if tick_low == tick_high:
        return int(tick_low)
    else:
        if getSqrtRatioAtTick(tick_high) <= sqrtRatioX96:
            return int(tick_high)
        else:
            return int(tick_low)

# https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/utils/encodeSqrtRatioX96.ts
def encodeSqrtRatioX96(amount_1: Wad, amount_0: Wad) -> int:
    """ Returns a uint160 composed from the ratio of amount1/amount0 """
    assert (isinstance(amount_1, Wad))
    assert (isinstance(amount_0, Wad))

    numerator = amount_1 << 196
    
    ratio_x_192 = numerator / amount_0
    return sqrt(ratio_x_192)

# TODO: finish implementing
# https://github.com/Uniswap/uniswap-v3-sdk/blob/c8e0d4c56e3b3ebd6446aba66523d20f2ea0fd9c/src/utils/nearestUsableTick.ts
def nearest_usable_tick(tick: int, tick_spacing: int) -> float:
    assert (isinstance(tick, int))
    assert (isinstance(tick_spacing, int))
