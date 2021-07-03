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

from pyexchange.uniswapv3_constants import Q96, Q192, MAX_SQRT_RATIO, MIN_SQRT_RATIO, MAX_UINT256, ZERO, ONE, MAX_FEE, \
    MAX_UINT160
from pymaker.numeric import Wad
from fxpmath import Fxp
from typing import List, Tuple

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

# https://stackoverflow.com/questions/141525/what-are-bitwise-shift-bit-shift-operators-and-how-do-they-work
# https://realpython.com/python-bitwise-operators/

# https://www.geeksforgeeks.org/find-significant-set-bit-number/
# https://www.baeldung.com/cs/most-significant-bit
from pyexchange.uniswapv3_entities import Tick


def most_significant_bit(x: int) -> int:
    """ returns the most significant bit for a given number """
    assert (isinstance(x, int))
    return int(math.log(x, 2))

# TODO: check return type
def mul_shift(value: int, multiply_by: str) -> int:
    """ multiply_by is assumed to be a hex encoded base16 number """
    assert (isinstance(value, int))
    assert (isinstance(multiply_by, str))

    # signed right shift
    number = (value * int(multiply_by, 16)) >> 128
    return number

def get_sqrt_ratio_at_tick(tick: int) -> int:
    assert (isinstance(tick, int))

    abs_tick = tick * - 1 if tick < 0 else tick

    ratio = int('0xfffcb933bd6fad37aa2d162d1a594001', 16) if (abs_tick & int('0x1', 16)) != 0 else int('0x100000000000000000000000000000000', 16)

    if abs_tick & int('0x2', 16) != 0:
        ratio = mul_shift(ratio, '0xfff97272373d413259a46990580e213a')
    if abs_tick & int('0x4', 16) != 0:
        ratio = mul_shift(ratio, '0xfff2e50f5f656932ef12357cf3c7fdcc')
    if abs_tick & int('0x8', 16) != 0:
        ratio = mul_shift(ratio, '0xffe5caca7e10e4e61c3624eaa0941cd0')
    if abs_tick & int('0x10', 16) != 0:
        ratio = mul_shift(ratio, '0xffcb9843d60f6159c9db58835c926644')
    if abs_tick & int('0x20', 16) != 0:
        ratio = mul_shift(ratio, '0xff973b41fa98c081472e6896dfb254c0')
    if abs_tick & int('0x40', 16) != 0:
        ratio = mul_shift(ratio, '0xff2ea16466c96a3843ec78b326b52861')
    if abs_tick & int('0x80', 16) != 0:
        ratio = mul_shift(ratio, '0xfe5dee046a99a2a811c461f1969c3053')
    if abs_tick & int('0x100', 16) != 0:
        ratio = mul_shift(ratio, '0xfcbe86c7900a88aedcffc83b479aa3a4')
    if abs_tick & int('0x200', 16) != 0:
        ratio = mul_shift(ratio, '0xf987a7253ac413176f2b074cf7815e54')
    if abs_tick & int('0x400', 16) != 0:
        ratio = mul_shift(ratio, '0xf3392b0822b70005940c7a398e4b70f3')
    if abs_tick & int('0x800', 16) != 0:
        ratio = mul_shift(ratio, '0xe7159475a2c29b7443b29c7fa6e889d9')
    if abs_tick & int('0x1000', 16) != 0:
        ratio = mul_shift(ratio, '0xd097f3bdfd2022b8845ad8f792aa5825')
    if abs_tick & int('0x2000', 16) != 0:
        ratio = mul_shift(ratio, '0xa9f746462d870fdf8a65dc1f90e061e5')
    if abs_tick & int('0x4000', 16) != 0:
        ratio = mul_shift(ratio, '0x70d869a156d2a1b890bb3df62baf32f7')
    if abs_tick & int('0x8000', 16) != 0:
        ratio = mul_shift(ratio, '0x31be135f97d08fd981231505542fcfa6')
    if abs_tick & int('0x10000', 16) != 0:
        ratio = mul_shift(ratio, '0x9aa508b5b7a84e1c677de54f3e99bc9')
    if abs_tick & int('0x20000', 16) != 0:
        ratio = mul_shift(ratio, '0x5d6af8dedb81196699c329225ee604')
    if abs_tick & int('0x40000', 16) != 0:
        ratio = mul_shift(ratio, '0x2216e584f5fa1ea926041bedfe98')
    if abs_tick & int('0x80000', 16) != 0:
        ratio = mul_shift(ratio, '0x48a170391f7dc42444e8fa2')

    if tick > 0:
        ratio = int(MAX_UINT256 / ratio)

    q32 = 2 ** 32

    # convert back to Q64.96
    if ratio % q32 >= ZERO:
        return int((ratio / q32) + ZERO)
    else:
        return int(ratio / q32)

# https://github.com/Uniswap/uniswap-v3-sdk/blob/c8e0d4c56e3b3ebd6446aba66523d20f2ea0fd9c/src/utils/tickMath.ts#L82
# TODO: add FXP Qm.n typing? Add signing?
# TODO: clean up Fxp instantiation / add constants -> add support for Fxp templates?
def get_tick_at_sqrt_ratio(sqrtRatioX96: int) -> int:
    """ return the tick for a given Q64.96 formatted ratio (64 bit word, 96 fractional bits)

        Used to get the amount of liquidity available in a position: 
     """
    assert (isinstance(sqrtRatioX96, int))

    # TODO: verify this shouldn't be << Fxp(32)
    square_root_ratio_x128 = sqrtRatioX96 << 32

    msb = most_significant_bit(square_root_ratio_x128)

    r = None
    if msb >= 128:
        # signed right shift
        r = square_root_ratio_x128 >> (msb - 127)
    else:
        # left shift
        # TODO: verify left shifted into Q64.64?
        r = square_root_ratio_x128 << (127 - msb)

    # TODO: figure out how to deal with sign... dealt with by Fxp internals?
    log_2 = (msb - 128) << 64

    # TODO: why is Fxp(Fxp) impactful in here?
    for i in range(14):
        # signed right shift
        r = (r * r) >> 127
        f = r >> 128

        # TODO: figure out why this is changing it's wordsize ... need to also be Fxp?
        # leftshift bitwise OR
        log_2 = log_2 | f << (63 - i)

        # signed right shift
        r = r >> f

    log_sqrt10001 = (log_2 * 255738958999603826347141)

    tick_low = (log_sqrt10001 - 3402992956809132418596140100660247210) >> 128
    tick_high = (log_sqrt10001 + 291339464771989622907027621153398088495) >> 128

    if tick_low == tick_high:
        return int(tick_low)
    else:
        if get_sqrt_ratio_at_tick(tick_high) <= sqrtRatioX96:
            return int(tick_high)
        else:
            return int(tick_low)

# TODO: determine proper type encoding -- is word size enforcable?
# https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/utils/encodeSqrtRatioX96.ts
def encodeSqrtRatioX96(amount_1: int, amount_0: int) -> int:
    """ Returns a Q64.96 uint160 composed from the ratio of amount1/amount0 """
    assert (isinstance(amount_1, int))
    assert (isinstance(amount_0, int))

    # TODO: figure out why this is returning 0
    # TODO: apply bitmask & 256 here to resolve potential wrapping issue?
    numerator = amount_1 << 192
    
    ratio_x_192 = numerator / amount_0

    return int(math.sqrt(ratio_x_192))

# TODO: finish implementing
# https://github.com/Uniswap/uniswap-v3-sdk/blob/c8e0d4c56e3b3ebd6446aba66523d20f2ea0fd9c/src/utils/nearestUsableTick.ts
def nearest_usable_tick(tick: int, tick_spacing: int) -> float:
    assert (isinstance(tick, int))
    assert (isinstance(tick_spacing, int))

def mul_div_rounding_up(a: int, b: int, denominator: int):
    assert (isinstance(a, int))
    assert (isinstance(b, int))
    assert (isinstance(denominator, int))
    
    product = a * b
    # TODO: does result need to be cast to int? currently returning a percentage here...
    result = product / denominator
    # TODO: check equality here
    if product % denominator != ZERO:
        result += ONE
    
    return int(result)

def compute_swap_step(sqrt_ratio_current_price_x96: int, sqrt_ratio_target_price_x96: int, liquidity: int, amount_remaining: int, fee_pips: int) -> Tuple:
    """ @returns {sqrt_price_next_x96, amount_in, amount_out, fee_amount} """
    assert isinstance(sqrt_ratio_current_price_x96, int)
    assert isinstance(sqrt_ratio_target_price_x96, int)
    assert isinstance(liquidity, int)
    assert isinstance(amount_remaining, int)
    assert isinstance(fee_pips, int)

    return_state = {}

    zero_or_one = sqrt_ratio_current_price_x96 > sqrt_ratio_target_price_x96
    exact_in = amount_remaining > 0

    if exact_in:
        amount_remaining_less_fee = (amount_remaining * (MAX_FEE - fee_pips)) / MAX_FEE
        if zero_or_one:
            return_state["amount_in"] = SqrtPriceMath.get_amount_0_delta(sqrt_ratio_target_price_x96, sqrt_ratio_current_price_x96, liquidity, True)
        else:
            return_state["amount_in"] = SqrtPriceMath.get_amount_1_delta(sqrt_ratio_current_price_x96, sqrt_ratio_target_price_x96, liquidity, True)

        assert return_state["amount_in"] is not None
        if amount_remaining_less_fee >= return_state["amount_in"]:
            return_state["sqrt_price_next_x96"] = sqrt_ratio_target_price_x96
        else:
            return_state["sqrt_price_next_x96"] = SqrtPriceMath.get_next_sqrt_price_from_input(sqrt_ratio_current_price_x96, liquidity, amount_remaining_less_fee, zero_or_one)
    else:
        if zero_or_one:
            return_state["amount_out"] = SqrtPriceMath.get_amount_1_delta(sqrt_ratio_target_price_x96, sqrt_ratio_current_price_x96, liquidity, False)
        else:
            return_state["amount_out"] = SqrtPriceMath.get_amount_0_delta(sqrt_ratio_current_price_x96, sqrt_ratio_target_price_x96, liquidity, False)

        if amount_remaining * -1 >= return_state["amount_out"]:
            return_state["sqrt_price_next_x96"] = sqrt_ratio_target_price_x96
        else:
            return_state["sqrt_price_next_x96"] = SqrtPriceMath.get_next_sqrt_price_from_output(sqrt_ratio_current_price_x96, liquidity, (amount_remaining * -1), zero_or_one)

    max = sqrt_ratio_target_price_x96 == return_state["sqrt_price_next_x96"]

    if zero_or_one:
        return_state["amount_in"] = return_state["amount_in"] if max and exact_in else SqrtPriceMath.get_amount_0_delta(return_state["sqrt_price_next_x96"], sqrt_ratio_current_price_x96, liquidity, True)

        return_state["amount_out"] = return_state["amount_out"] if max and not exact_in else SqrtPriceMath.get_amount_1_delta(return_state["sqrt_price_next_x96"], sqrt_ratio_current_price_x96, liquidity, False)
    else:
        return_state["amount_in"] = return_state["amount_in"] if max and exact_in else SqrtPriceMath.get_amount_1_delta(sqrt_ratio_current_price_x96, return_state["sqrt_price_next_x96"], liquidity, True)

        return_state["amount_out"] = return_state["amount_out"] if max and not exact_in else SqrtPriceMath.get_amount_0_delta(sqrt_ratio_current_price_x96, return_state["sqrt_price_next_x96"], liquidity, False)

    if not exact_in and return_state["amount_out"] > (amount_remaining * -1):
        return_state["amount_out"] = amount_remaining * -1

    if exact_in and return_state["sqrt_price_next_x96"] != sqrt_ratio_target_price_x96:
        return_state["fee_amount"] = amount_remaining - return_state["amount_in"]
    else:
        return_state["fee_amount"] = mul_div_rounding_up(return_state["amount_in"], fee_pips, MAX_FEE - fee_pips)

    # TODO: use tuple variables in place of return_state{}
    sqrt_price_next_x96 = return_state["sqrt_price_next_x96"]
    amount_in = return_state["amount_in"]
    amount_out = return_state["amount_out"]
    fee_amount = return_state["fee_amount"]

    return sqrt_price_next_x96, amount_in, amount_out, fee_amount

def multiply_bitwise_and_256(x: int, y: int) -> int:
    assert (isinstance(x, int))
    assert (isinstance(y, int))

    product = x * y
    return product & MAX_UINT256

def add_bitwise_and_256(x: int, y: int) -> int:
    assert (isinstance(x, int))
    assert (isinstance(y, int))

    sum = x + y
    return sum & MAX_UINT256

def add_liquidity_delta(x: int, y: int) -> int:
    assert (isinstance(x, int))
    assert (isinstance(y, int))

    if y < 0:
        return x - (y * - 1)
    else:
        return x + y

# TODO: rename this to TickList? group above methods into TickMath
class TickMath:

    @staticmethod
    def get_tick(ticks: List[Tick], tick_index: int) -> Tick:
        assert isinstance(ticks, List)
        assert isinstance(tick_index, int)

        tick = ticks[TickMath._find_largest_tick(ticks, tick_index)]
        # check that the given tick_index is contained within the list of initialized ticks
        assert tick.index == tick_index
        return tick

    @staticmethod
    def _is_below_smallest_tick(ticks: List, tick: int) -> bool:
        assert (isinstance(ticks, List) and len(ticks) > 0)
        assert isinstance(tick, int)

        return tick < ticks[0].index

    @staticmethod
    def _is_at_or_above_largest_tick(ticks: List, tick: int) -> bool:
        assert (isinstance(ticks, List) and len(ticks) > 0)
        assert isinstance(tick, int)

        return tick > ticks[len(ticks) - 1].index

    @staticmethod
    def _find_largest_tick(ticks: List, tick) -> int:
        """ Find index of largest tick in list that is less than or equal to given tick using binary search """
        assert (isinstance(ticks, List) and len(ticks) > 0)
        assert isinstance(tick, int)
        assert TickMath._is_below_smallest_tick(ticks, tick) is not True

        l = 0
        r = len(ticks) - 1
        # TODO: figure out best initialization state for i
        i = 0

        while True:
            i = math.floor((l + r) / 2)

            if ticks[i].index <= tick and (i == len(ticks) - 1 or ticks[i + 1].index > tick):
                return i

            if ticks[i].index < tick:
                l = i + 1
            else:
                r = i + 1

    @staticmethod
    def next_initialized_tick(ticks: List[Tick], tick: int, zero_or_one: bool) -> Tick:
        assert isinstance(ticks, List)
        assert isinstance(tick, int)
        assert isinstance(zero_or_one, bool)

        if zero_or_one:
            assert TickMath._is_below_smallest_tick(ticks, tick) is not True
            if TickMath._is_at_or_above_largest_tick(ticks, tick):
                return ticks[len(ticks) - 1]
            index = TickMath._find_largest_tick(ticks, tick)
            return ticks[index]
        else:
            assert TickMath._is_at_or_above_largest_tick(ticks, tick) is not True
            if TickMath._is_below_smallest_tick(ticks, tick):
                return ticks[0]
            index = TickMath._find_largest_tick(ticks, tick)
            return ticks[index + 1]

    @staticmethod
    def next_initialized_tick_within_word(ticks: List[Tick], tick: int, zero_or_one: bool, tick_spacing: int) -> Tuple:
        """ https://github.com/Uniswap/uniswap-v3-sdk/blob/19a990403817d0359d8f38edfa3b0827d32adc05/src/utils/tickList.ts#L101
            @returns (tick, tick_initalized)
        """
        assert isinstance(ticks, List)
        assert isinstance(tick, int)
        assert isinstance(zero_or_one, bool)
        assert isinstance(tick_spacing, int)

        compressed = math.floor(tick / tick_spacing)

        if zero_or_one:
            word_position = compressed >> 8
            minimum = (word_position << 8) * tick_spacing

            if TickMath._is_below_smallest_tick(ticks, tick):
                return (minimum, False)

            index = TickMath.next_initialized_tick(ticks, tick, zero_or_one).index
            next_initalized_tick = max(minimum, index)
            return (next_initalized_tick, next_initalized_tick == index)
        else:
            word_position = (compressed + 1) >> 8
            maximum = ((word_position + 1) << 8) * tick_spacing - 1

            if TickMath._is_at_or_above_largest_tick(ticks, tick):
                return (maximum, False)

            index = TickMath.next_initialized_tick(ticks, tick, zero_or_one).index
            next_initalized_tick = min(maximum, index)
            return (next_initalized_tick, next_initalized_tick == index)


class SqrtPriceMath:

    @staticmethod
    def invert_ratio_if_needed(sqrtRatioAX96: int, sqrtRatioBX96: int) -> Tuple:
        assert (isinstance(sqrtRatioAX96, int))
        assert (isinstance(sqrtRatioBX96, int))

        if sqrtRatioAX96 > sqrtRatioBX96:
            old_sqrtRatioBX96 = sqrtRatioBX96
            old_sqrtRatioAX96 = sqrtRatioAX96
            sqrtRatioAX96 = old_sqrtRatioBX96
            sqrtRatioBX96 = old_sqrtRatioAX96

        return sqrtRatioAX96, sqrtRatioBX96

    @staticmethod
    def get_amount_0_delta(sqrtRatioAX96: int, sqrtRatioBX96: int, liquidity: int, round_up: bool) -> Wad:
        assert (isinstance(sqrtRatioAX96, int))
        assert (isinstance(sqrtRatioBX96, int))
        assert (isinstance(liquidity, int))
        assert (isinstance(round_up, bool))
        
        sqrtRatioAX96, sqrtRatioBX96 = SqrtPriceMath.invert_ratio_if_needed(sqrtRatioAX96, sqrtRatioBX96)
        
        numerator_1 = int(liquidity << 96)
        numerator_2 = sqrtRatioBX96 - sqrtRatioAX96

        # TODO: cast back to int?
        if round_up:
            return mul_div_rounding_up(mul_div_rounding_up(numerator_1, numerator_2, sqrtRatioBX96), ONE, sqrtRatioAX96)
        else:
            return ((numerator_1 * numerator_2) / sqrtRatioBX96) / sqrtRatioAX96

    @staticmethod
    def get_amount_1_delta(sqrtRatioAX96: int, sqrtRatioBX96: int, liquidity: int, round_up: bool) -> Wad:
        assert (isinstance(sqrtRatioAX96, int))
        assert (isinstance(sqrtRatioBX96, int))
        assert (isinstance(liquidity, int))
        assert (isinstance(round_up, bool))

        sqrtRatioAX96, sqrtRatioBX96 = SqrtPriceMath.invert_ratio_if_needed(sqrtRatioAX96, sqrtRatioBX96)
        
        if round_up:
            return mul_div_rounding_up(liquidity, (sqrtRatioBX96 - sqrtRatioAX96), Q96)
        else:
            return (liquidity * (sqrtRatioBX96 - sqrtRatioAX96)) / Q96

    @staticmethod
    def get_next_sqrt_price_from_input(sqrt_price_x96: int, liquidity: int, amount_in: int, zero_or_one: bool):
        assert (isinstance(sqrt_price_x96, int) and sqrt_price_x96 > 0)
        assert (isinstance(liquidity, int) and liquidity > 0)
        assert (isinstance(amount_in, int))
        assert (isinstance(zero_or_one, bool))

        if zero_or_one:
            return SqrtPriceMath.get_next_sqrt_price_from_amount_1_rounding_down(sqrt_price_x96, liquidity, amount_in, True)
        else:
            return SqrtPriceMath.get_next_sqrt_price_from_amount_0_rounding_up(sqrt_price_x96, liquidity, amount_in, True)

    @staticmethod
    def get_next_sqrt_price_from_output(sqrt_price_x96: int, liquidity: int, amount_out: int, zero_or_one: bool):
        assert (isinstance(sqrt_price_x96, int) and sqrt_price_x96 > 0)
        assert (isinstance(liquidity, int) and liquidity > 0)
        assert (isinstance(amount_out, int))
        assert (isinstance(zero_or_one, bool))

        if zero_or_one:
            return SqrtPriceMath.get_next_sqrt_price_from_amount_1_rounding_down(sqrt_price_x96, liquidity, amount_out, True)
        else:
            return SqrtPriceMath.get_next_sqrt_price_from_amount_0_rounding_up(sqrt_price_x96, liquidity, amount_out, True)

    @staticmethod
    def get_next_sqrt_price_from_amount_0_rounding_up(sqrt_price_x96: int, liquidity: int, amount: int, add: bool) -> int:
        assert (isinstance(sqrt_price_x96, int))
        assert (isinstance(liquidity, int))
        assert (isinstance(amount, int))
        assert (isinstance(add, bool))

        if amount == 0:
            return sqrt_price_x96

        numerator_1 =  liquidity << 96

        if add:
            product = multiply_bitwise_and_256(amount, sqrt_price_x96)
            if product / amount == sqrt_price_x96:
                denominator = add_bitwise_and_256(numerator_1, product)
                if denominator >= numerator_1:
                    return mul_div_rounding_up(numerator_1, sqrt_price_x96, denominator)
            return mul_div_rounding_up(numerator_1, 1, (numerator_1 / sqrt_price_x96) + amount)
        else:
            product = multiply_bitwise_and_256(amount, sqrt_price_x96)

            assert (product / amount) == sqrt_price_x96
            assert numerator_1 > product

            denominator = numerator_1 - product
            return mul_div_rounding_up(numerator_1, sqrt_price_x96, denominator)

    @staticmethod
    def get_next_sqrt_price_from_amount_1_rounding_down(sqrt_price_x96: int, liquidity: int, amount: int, add: bool) -> int:
        assert (isinstance(sqrt_price_x96, int))
        assert (isinstance(liquidity, int))
        assert (isinstance(amount, int))
        assert (isinstance(add, bool))

        if add:
            if amount <= MAX_UINT160:
                quotient = (amount << 96) / liquidity
            else:
                quotient = (amount * Q96) / liquidity

            return sqrt_price_x96 + quotient
        else:
            quotient = mul_div_rounding_up(amount, Q96, liquidity)

            assert sqrt_price_x96 > quotient
            return sqrt_price_x96 - quotient