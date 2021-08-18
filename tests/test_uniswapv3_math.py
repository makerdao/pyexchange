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
import time

import pytest

from pyexchange.uniswapv3_entities import Fraction
from pyexchange.uniswapv3_constants import MIN_SQRT_RATIO, MAX_SQRT_RATIO, MIN_TICK, MAX_TICK, Q96, FEES, TICK_SPACING
from pyexchange.uniswapv3_math import get_tick_at_sqrt_ratio, get_sqrt_ratio_at_tick, encodeSqrtRatioX96, Tick


def test_get_tick_at_sqrt_ratio():
    calculated_sqrt_price_ratio = encodeSqrtRatioX96(1, 1900)
    sqrt_price_ratio_expected = 1817618704642608503278368873

    assert calculated_sqrt_price_ratio == sqrt_price_ratio_expected

    tick = get_tick_at_sqrt_ratio(calculated_sqrt_price_ratio)

    assert tick == -75500
    assert get_tick_at_sqrt_ratio(MIN_SQRT_RATIO) == MIN_TICK
    assert get_tick_at_sqrt_ratio(MAX_SQRT_RATIO - 1) == MAX_TICK - 1

def test_sqrt_ratio_at_tick():
    assert get_sqrt_ratio_at_tick(MIN_TICK) == MIN_SQRT_RATIO
    assert get_sqrt_ratio_at_tick(MAX_TICK) == MAX_SQRT_RATIO


def test_encode_srt_ratio():
    assert encodeSqrtRatioX96(1, 1) == Q96
    assert encodeSqrtRatioX96(100, 1) == 792281625142643375935439503360
    assert encodeSqrtRatioX96(1, 100) == 7922816251426433759354395033
    assert encodeSqrtRatioX96(111, 333) == 45742400955009932534161870629
    assert encodeSqrtRatioX96(333, 111) == 137227202865029797602485611888

def test_nearest_usable_tick():
    # given
    current_tick = 74999
    tick_spacing = TICK_SPACING.MEDIUM.value

    # when
    rounded_tick = Tick.nearest_usable_tick(current_tick, tick_spacing)

    # then
    assert rounded_tick % tick_spacing == 0


def test_fraction_add():
    fraction_1 = Fraction(20, 100)
    fraction_2 = Fraction(30, 100)

    output_fraction = fraction_1.add(fraction_2)

    assert output_fraction.float_quotient() == .5


def test_fraction_subtract():
    fraction_1 = Fraction(50, 100)
    fraction_2 = Fraction(30, 100)

    output_fraction = fraction_1.subtract(fraction_2)

    assert output_fraction.float_quotient() == .2


def test_fraction_multiply():
    fraction_1 = Fraction(20, 100)
    fraction_2 = Fraction(30, 100)

    output_fraction = fraction_1.multiply(fraction_2)

    assert output_fraction.float_quotient() == .06


def test_fraction_divide():
    fraction_1 = Fraction(60, 100)
    fraction_2 = Fraction(30, 100)

    output_fraction = fraction_1.divide(fraction_2)

    assert output_fraction.float_quotient() == 2
