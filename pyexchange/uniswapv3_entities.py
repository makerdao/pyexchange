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

from fractions import Fraction
from fxpmath import Fxp
from typing import List, Optional, Tuple
from web3 import Web3

from pyexchange.uniswapv3_math import encodeSqrtRatioX96, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, next_initialized_tick, SqrtPriceMath
from pyexchange.uniswapv3_constants import Q192, MAX_SQRT_RATIO, MIN_SQRT_RATIO, Q96, MIN_TICK, MAX_TICK, TICK_SPACING
from pymaker import Address, Calldata, Invocation
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.util import bytes_to_int, bytes_to_hexstring, int_to_bytes32


# TODO: add scaling based upon token decimals
class PriceFraction:

    def __init__(self, base_token: Token, quote_token: Token, denominator: int, numerator: int):
        assert isinstance(base_token, Token)
        assert isinstance(quote_token, Token)

        self.base_token = base_token
        self.quote_token = quote_token
        # TODO: best place to normalize? leave this as wad as opposed to converting back to int?
        # TODO: unfuck this normalization
        # self.numerator = self.quote_token.normalize_amount(Wad.from_number(numerator)).value # quote token
        # self.denominator = self.base_token.normalize_amount(Wad.from_number(denominator)).value # base token

        self.numerator = self.quote_token.normalize_amount(Wad.from_number(numerator)).value  # quote token
        self.denominator = self.base_token.normalize_amount(Wad.from_number(denominator)).value  # base token

    def get_float_price(self) -> float:
        return float(self.numerator / self.denominator)
    
    def multiply(self, other):
        """ multiply two PriceFractions together. This method assumes that the other's base currency matches self's quote currency

            returns a new PriceFraction instance with the resultant numerator and denominator.
        """
        numerator_result = self.numerator * other.numerator
        denominator_result = self.denominator * other.denominator

        return self.__class__(self.base_token, other.quote_token, numerator_result, denominator_result)

    @staticmethod
    def convert_to_fraction(number) -> Fraction:
        """ https://stackoverflow.com/questions/23344185/how-to-convert-a-decimal-number-into-fraction """

        return Fraction(str(number))
    
    @staticmethod
    def from_fraction(fraction: Fraction, base_token: Token, quote_token: Token):
        assert isinstance(fraction, Fraction)
        assert isinstance(base_token, Token)
        assert isinstance(quote_token, Token)

        return PriceFraction(base_token, quote_token, fraction.denominator, fraction.numerator)


class Pool:
    """ https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/entities/pool.ts """
    def __init__(self, token_0: Token, token_1: Token, fee: int, square_root_ratio_x96: int, liquidity: int, tick_current: int, ticks: List):
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)
        assert isinstance(fee, int)
        assert isinstance(square_root_ratio_x96, int)
        assert isinstance(liquidity, int)
        assert isinstance(tick_current, int)
        # TODO: remove None check?
        assert (isinstance(ticks, List) or (ticks is None))

        self.token_0 = token_0
        self.token_1 = token_1
        self.fee = fee
        self.square_root_ratio_x96 = square_root_ratio_x96
        self.liquidity = liquidity
        self.tick_current = tick_current
        self.ticks = ticks
        self.token_0_price = self.get_token_0_price()
        self.token_1_price = self.get_token_1_price()
        self.tick_spacing = TICK_SPACING[f"{fee}"].value

    def get_token_0_price(self) -> PriceFraction:
        # base, quote
        return PriceFraction(self.token_0, self.token_1, Q192, (self.square_root_ratio_x96 * self.square_root_ratio_x96))

    # TODO: verify proper return type here -- wad desired?
    def get_token_1_price(self) -> PriceFraction:
        return PriceFraction(self.token_0, self.token_1, (self.square_root_ratio_x96 * self.square_root_ratio_x96), Q192)

    def get_output_amount(self, input_amount: int, sqrt_price_limit_x96: int) -> int:
        assert isinstance(input_amount, int)
        assert isinstance(sqrt_price_limit_x96, int)

    def get_input_amount(self) -> int:
        pass

    def swap(self, zero_or_one: bool, swap_amount: int, sqrt_price_limit_x96: int) -> dict:
        """ Calculate a swap and output pool state
            @param zero_or_one boolean indicating swapping in token_0 or token_1
            @param swap_amount integer amount of the given token to be swapped
            @param sqrt_price_limit_x96 price limit that can't be breached following swap reserve changes
            @returns dictionary of resulting pool state {amount_calculated, sqrt_price_ratio_x96, liquidity, tick_current}
        """
        assert isinstance(zero_or_one, bool)
        assert isinstance(swap_amount, int)
        assert isinstance(sqrt_price_limit_x96, int)

        # TODO: pass in MIN or MAX SQRT RATIO to establish default price limits
        if sqrt_price_limit_x96 is None:
           pass

        if zero_or_one:
            assert sqrt_price_limit_x96 > MIN_SQRT_RATIO
            assert sqrt_price_limit_x96 < self.square_root_ratio_x96
        else:
            assert sqrt_price_limit_x96 < MAX_SQRT_RATIO
            assert sqrt_price_limit_x96 > self.square_root_ratio_x96

        pool_swap_state = {
            "swap_amount_remaining": swap_amount,
            "amount_calculated": 0,
            "sqrt_price_x96": self.square_root_ratio_x96,
            "tick": self.tick_current,
            "liquidity": self.liquidity
        }

        while pool_swap_state["swap_amount_remaining"] != 0 and pool_swap_state["sqrt_price_x96"] != sqrt_price_limit_x96:

            tick_next, tick_initalized = next_initalized_tick(pool_swap_state["tick"], zero_or_one, self.tick_spacing)

            step_state = {
                "sqrt_price_x96": pool_swap_state["sqrt_price_x96"],
                "tick_next": tick_next,
                "tick_initalized": tick_initalized
            }

            if step_state["tick_next"] < MIN_TICK:
                step_state["tick_next"] = MIN_TICK
            elif step_state["tick_next"] > MAX_TICK:
                step_state["tick_next"] = MAX_TICK



class Position:

    # TODO: check the integer precision of liquidity
    def __init__(self, pool: Pool, tick_lower: int, tick_upper: int, liquidity: int):
        """ https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/entities/position.ts """
        assert isinstance(pool, Pool)
        assert isinstance(tick_lower, int)
        assert isinstance(tick_upper, int)
        assert isinstance(liquidity, int)

        self.pool = pool
        self.tick_lower = tick_lower
        self.tick_upper = tick_upper
        self.liquidity = liquidity

        self.token_0_amount = None
        self.token_1_amount = None
        self._mint_amounts: Tuple = None # Tuple

    def get_token_0_price_lower(self):
        """ return the token_0 price at the lower tick """
        pass

    def get_token_0_price_upper(self):
        """ return the token_0 price at the upper tick """
        pass

    def amount_in_token_0(self) -> Wad:
        """ Returns the amount of token0 that this position's liquidity could be burned for at the current pool price """
        if self.token_0_amount == None:
            if self.pool.tick_current < self.tick_lower:
                self.token_0_amount = SqrtPriceMath.get_amount_0_delta(
                    get_sqrt_ratio_at_tick(self.tick_lower),
                    get_sqrt_ratio_at_tick(self.tick_upper),
                    self.liquidity,
                    False
                )
            elif self.pool.tick_current < self.tick_upper:
                self.token_0_amount = SqrtPriceMath.get_amount_0_delta(
                    get_sqrt_ratio_at_tick(self.tick_lower),
                    get_sqrt_ratio_at_tick(self.tick_upper),
                    self.liquidity,
                    False
                )
            else:
                self.token_0_amount = Wad.from_number(0)

    def amount_in_token_1(self) -> Wad:
        """ """
        pass

    @staticmethod
    def max_liquidity_for_amount_0(sqrtRatioAX96: int, sqrtRatioBX96: int, amount_0: int, use_full_precision: bool) -> int:
        assert (isinstance(sqrtRatioAX96, int))
        assert (isinstance(sqrtRatioBX96, int))
        # assert (isinstance(amount_0, int))
        assert (isinstance(use_full_precision, bool))

        sqrtRatioAX96, sqrtRatioBX96 = SqrtPriceMath.invert_ratio_if_needed(sqrtRatioAX96, sqrtRatioBX96)

        if use_full_precision:
            numerator = (amount_0 * sqrtRatioAX96) * sqrtRatioBX96
            denominator = Q96 * (sqrtRatioBX96 - sqrtRatioAX96)
            result = int(numerator / denominator)
            return result
        else:
            intermediate = (sqrtRatioAX96 * sqrtRatioBX96) / Q96
            result = int((amount_0 * intermediate) / (sqrtRatioBX96 - sqrtRatioAX96))
            return result

    @staticmethod
    def max_liquidity_for_amount_1(sqrtRatioAX96: int, sqrtRatioBX96: int, amount_1: int) -> int:
        assert (isinstance(sqrtRatioAX96, int))
        assert (isinstance(sqrtRatioBX96, int))
        # assert (isinstance(amount_1, int))

        sqrtRatioAX96, sqrtRatioBX96 = SqrtPriceMath.invert_ratio_if_needed(sqrtRatioAX96, sqrtRatioBX96)

        result = int((amount_1 * Q96) / (sqrtRatioBX96 - sqrtRatioAX96))
        return result

    # TODO: move these methods to uniswapv3_math?
    # TODO: remove top level usage of SqrtPriceMath.invert_ratio_if_needed(sqrtRatioAX96, sqrtRatioBX96)?
    @staticmethod
    def max_liquidity_for_amounts(pool: Pool, sqrt_ratio_current_x96: int, sqrtRatioAX96: int, sqrtRatioBX96: int, amount_0: int, amount_1: int, use_full_precision: bool) -> int:
        assert (isinstance(pool, Pool))
        assert (isinstance(sqrtRatioAX96, int))
        assert (isinstance(sqrtRatioBX96, int))
        # assert (isinstance(amount_0, int))
        # assert (isinstance(amount_1, int))
        assert (isinstance(use_full_precision, bool))

        sqrtRatioAX96, sqrtRatioBX96 = SqrtPriceMath.invert_ratio_if_needed(sqrtRatioAX96, sqrtRatioBX96)

        # TODO: determine if there's a decimal issue with sqrt_ratio_current_x96
        if sqrt_ratio_current_x96 <= sqrtRatioAX96:
            return Position.max_liquidity_for_amount_0(sqrtRatioAX96, sqrtRatioBX96, amount_0, use_full_precision)
        elif sqrt_ratio_current_x96 < sqrtRatioBX96:
            liquidity_0 = Position.max_liquidity_for_amount_0(sqrtRatioAX96, sqrtRatioBX96, amount_0, use_full_precision)
            liquidity_1 = Position.max_liquidity_for_amount_1(sqrtRatioAX96, sqrtRatioBX96, amount_1)
            # determine maximum amount of liquidity that doesn't exceed other side
            return liquidity_0 if liquidity_0 < liquidity_1 else liquidity_1
        else:
            # TODO: figure out why amount_1 is 0?
            return Position.max_liquidity_for_amount_1(sqrtRatioAX96, sqrtRatioBX96, amount_1)

    @staticmethod
    def from_amounts(pool: Pool, tick_lower: int, tick_upper: int, amount_0, amount_1, use_full_precision):
        """ """
        assert (isinstance(pool, Pool))
        assert (isinstance(tick_lower, int))
        assert (isinstance(tick_upper, int))

        sqrtRatioAX96 = get_sqrt_ratio_at_tick(tick_lower)
        sqrtRatioBX96 = get_sqrt_ratio_at_tick(tick_upper)

        return Position(pool, tick_lower, tick_upper, Position.max_liquidity_for_amounts(
            pool,
            pool.square_root_ratio_x96,
            sqrtRatioAX96,
            sqrtRatioBX96,
            amount_0,
            amount_1,
            use_full_precision
        ))

    def mint_amounts(self) -> Tuple:
        if self._mint_amounts == None:
            if self.pool.tick_current < self.tick_lower:
                amount_0_delta = SqrtPriceMath.get_amount_0_delta(get_sqrt_ratio_at_tick(self.tick_lower), get_sqrt_ratio_at_tick(self.tick_upper), self.liquidity, True)
                amount_1_delta = 0
                self._mint_amounts = amount_0_delta, amount_1_delta

                return self._mint_amounts
            elif self.pool.tick_current < self.tick_upper:
                amount_0_delta = SqrtPriceMath.get_amount_0_delta(self.pool.square_root_ratio_x96, get_sqrt_ratio_at_tick(self.tick_upper), self.liquidity, True)
                amount_1_delta = SqrtPriceMath.get_amount_1_delta(get_sqrt_ratio_at_tick(self.tick_upper), self.pool.square_root_ratio_x96, self.liquidity, True)
                self._mint_amounts = amount_0_delta, amount_1_delta
                
                return self._mint_amounts
            else:
                amount_0_delta = 0
                amount_1_delta = SqrtPriceMath.get_amount_1_delta(get_sqrt_ratio_at_tick(self.tick_lower), get_sqrt_ratio_at_tick(self.tick_upper), self.liquidity, True)
                self._mint_amounts = amount_0_delta, amount_1_delta

                return self._mint_amounts
        else:
            return self._mint_amounts

    # TODO: determine if conversion to fractions is necessary
    def _ratios_after_slippage(self, slippage_tolerance: float) -> Tuple:
        assert isinstance(slippage_tolerance, float)
        assert (slippage_tolerance < 1 and slippage_tolerance > 0)

        price_lower = self.pool.get_token_0_price().multiply(PriceFraction.from_fraction(PriceFraction.convert_to_fraction((1 - slippage_tolerance)), self.pool.token_0, self.pool.token_1))
        price_upper = self.pool.get_token_0_price().multiply(PriceFraction.from_fraction(PriceFraction.convert_to_fraction((1 + slippage_tolerance)), self.pool.token_0, self.pool.token_1))

        sqrtRatioX96Lower = encodeSqrtRatioX96(price_lower.numerator, price_lower.denominator)

        if sqrtRatioX96Lower < MIN_SQRT_RATIO:
            sqrtRatioX96Lower = MIN_SQRT_RATIO + 1

        sqrtRatioX96Upper = encodeSqrtRatioX96(price_upper.numerator, price_upper.denominator)

        if sqrtRatioX96Upper > MAX_SQRT_RATIO:
            sqrtRatioX96Upper = MAX_SQRT_RATIO - 1

        return (sqrtRatioX96Lower, sqrtRatioX96Upper)

    def mint_amounts_with_slippage(self, slippage_tolerance: float) -> Tuple:
        """ Returns amount0; amount1 to mint after accounting for the given slippage_tolerance

            Virtual pools are created for instantiating Position entities that can be used to determin
        """

        sqrtRatioX96Lower, sqrtRatioX96Upper = self._ratios_after_slippage(slippage_tolerance)

        # create counterfactual pools with no liquidity
        pool_lower = Pool(self.pool.token_0, self.pool.token_1, self.pool.fee, sqrtRatioX96Lower, 0, get_tick_at_sqrt_ratio(sqrtRatioX96Lower), [])
        pool_upper = Pool(self.pool.token_0, self.pool.token_1, self.pool.fee, sqrtRatioX96Upper, 0, get_tick_at_sqrt_ratio(sqrtRatioX96Upper), [])

        position_to_create_amount_0, position_to_create_amount_1 = self.mint_amounts()
        position_to_create = Position.from_amounts(self.pool, self.tick_lower, self.tick_upper, position_to_create_amount_0, position_to_create_amount_1, False)

        # amount_0 = Position(pool_upper, self.tick_lower, self.tick_upper, position_to_create.liquidity).mint_amounts()[0]
        # amount_1 = Position(pool_lower, self.tick_lower, self.tick_upper, position_to_create.liquidity).mint_amounts()[1]
        # TODO: figure out why this worksish?
        # using position_to_create.liquidity results in reversed amounts...
        amount_0 = Position(pool_upper, self.tick_lower, self.tick_upper, 1).mint_amounts()[0]
        amount_1 = Position(pool_lower, self.tick_lower, self.tick_upper, 1).mint_amounts()[1]
        return amount_0, amount_1

    # TODO: is this still necessary?
    def as_NFT(self):
        """ return erc-721 representation of position"""
        pass


class Route:
    """ """
    def __init__(self, pools: List[Pool], input_token: Token, output_token: Token):
        assert isinstance(pools, List)
        assert isinstance(input_token, Token)
        assert isinstance(output_token, Token)

        token_path = []

        # normalize token path ordering for base-quote
        for pool in pools:
            token_path.push()

        self.pools = pools
        self.tokenPath = token_path
        self.input = input_token
        # Coalesce Nullish
        self.output = output_token or token_path[(token_path) - 1]



class Trade:
    """ Trade object representing a potential UniswapV3 Swap """
    def __init__(self, route: Route, input_amount: int, output_amount: int, trade_type):
        assert isinstance(route, Route)
        assert isinstance(input_amount, int)
        assert isinstance(output_amount, int)

        self.

    # TODO: make trade types an explicit enum?
    @staticmethod
    def from_route(self, route: Route, amount, trade_type: str):
        if trade_type == "exactInput":
            for step in route:
                pool = route[step]
                output_amount = pool.get_output_amount()

            input_amount = PriceFraction()
        return Trade()