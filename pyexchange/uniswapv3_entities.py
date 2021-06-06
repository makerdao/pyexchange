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


from typing import List, Optional
from web3 import Web3

from pymaker import Address, Calldata, Invocation
from pymaker.model import Token
from pymaker.numeric import Wad


class Params:

    def convert_to_bytes(self, calldata: Calldata) -> bytes:
        """ convert calldata to byte array """
        return calldata.as_bytes()

    def encode_calldata(self, web3: Web3, fn_signature: str, arguments: List) -> Calldata:
        """ encode inputted contract and methods with call arguments as pymaker.Calldata """
        assert isinstance(web3, Web3)
        assert isinstance(fn_signature, str)
        assert isinstance(arguments, List)

        # TODO: add Invocation support
        return Calldata.from_signature(web3, fn_signature, arguments)

    # TODO: remove method if unnecessary?
    # TODO: figure out how to handle multicall calldata
    @staticmethod
    def prepare_invocation(contract_address: Address, calldata: Calldata):
        return Invocation(contract_address, calldata)

    def _deadline(self) -> int:
        """Get a predefined deadline."""
        return int(time.time()) + 1000


class Pool:
    """ https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/entities/pool.ts """
    def __init__(self, token_0: Token, token_1: Token, fee: int, square_root_ratio_x96: Wad, liquidity: Wad, tick_current: int, ticks: List):
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)
        assert isinstance(fee, int)
        assert isinstance(square_root_ratio_x96, Wad)
        assert isinstance(liquidity, Wad)
        assert isinstance(tick_current, int)
        assert isinstance(ticks, List)

        self.token_0 = token_0
        self.token_1 = token_1
        self.fee = fee
        self.square_root_ratio_x96 = square_root_ratio_x96
        self.liquidity = liquidity
        self.tick_current = tick_current
        self.ticks = ticks


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
        self.mint_amounts: Tuple = None # Tuple

    def get_token_0_price_lower(self):
        """ return the token_0 price at the lower tick """
        pass

    def get_token_0_price_upper(self):
        """ return the token_0 price at the upper tick """
        pass

    def mint_amounts_with_slippage(self, slippage_tolerance: float) -> Tuple:
        """ Returns amount0; amount1 to mint """
        pass

    # TODO: is this still necessary?
    def as_NFT(self):
        """ return erc-721 representation of position"""
        pass