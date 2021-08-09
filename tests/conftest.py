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
from typing import List

import pytest

from web3 import Web3, HTTPProvider

# from pyexchange.uniswapv3 import PositionManager, SwapRouter
from pymaker import Address, Contract, web3_via_http
from pymaker.keys import register_keys, register_private_key

# def deploy_contracts():
from pymaker.model import Token
from pymaker.numeric import Wad
from pyexchange.uniswapv3 import PositionManager
from pyexchange.uniswapv3_calldata_params import MintParams
from pyexchange.uniswapv3_constants import FEES
from pyexchange.uniswapv3_entities import Pool, Position, Fraction


class PriceTickRatios:

    starting_sqrt_price = (1900, 1)

def price_tick_ratios():
    return PriceTickRatios


# https://stackoverflow.com/a/42156088
# https://towardsdatascience.com/testing-best-practices-for-machine-learning-libraries-41b7d0362c95
class PositionManagerHelpers:

    def __init__(self, web3: Web3, position_manager: PositionManager, position_manager_abi: List, token_0: Token, token_1: Token):
        assert isinstance(web3, Web3)
        assert isinstance(position_manager, PositionManager)
        assert isinstance(position_manager_abi, List)
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)

        self.web3 = web3
        self.position_manager = position_manager
        self.position_manager_abi = position_manager_abi
        self.token_0 = token_0
        self.token_1 = token_1

    def create_and_initialize_pool(self, starting_sqrt_price_x96: int, fee: int) -> Pool:
        assert isinstance(starting_sqrt_price_x96, int)
        assert isinstance(fee, int)

        token_0, token_1 = self.position_manager._set_address_order(self.token_0, self.token_1)
        create_pool_receipt = self.position_manager.create_pool(token_0, token_1, fee, starting_sqrt_price_x96).transact()

        assert create_pool_receipt is not None and create_pool_receipt.successful

        initialized_price = create_pool_receipt.result[0].sqrt_price_x96
        initialized_tick = create_pool_receipt.result[0].tick
        liquidity = 0  # liquidity is 0 upon initalization

        pool = Pool(
            token_0,
            token_1,
            fee,
            initialized_price,
            liquidity,
            initialized_tick,
            []
        )
        return pool

    def generate_mint_params(self, pool: Pool, position: Position, recipient: Address, slippage_tolerance: Fraction) -> MintParams:
        assert isinstance(pool, Pool)
        assert isinstance(position, Position)
        assert isinstance(recipient, Address)
        assert isinstance(slippage_tolerance, Fraction)

        deadline = int(time.time()) + 1000

        mint_params = MintParams(self.web3, self.position_manager_abi, position, recipient, slippage_tolerance, deadline)
        return mint_params

    def wrap_eth(self, wrap_amount: Wad, address: Address) -> int:
        """ deposit an input amount of weth and return the current weth balance of the given address"""
        assert isinstance(wrap_amount, Wad)

        deposit_eth_receipt = self.position_manager.wrap_eth(Wad.from_number(1)).transact(from_address=address)
        assert deposit_eth_receipt is not None and deposit_eth_receipt.successful
        weth_balance = self.position_manager.weth_contract.functions.balanceOf(address.address).call()
        assert weth_balance > 0
        # assert Wad.from_number(weth_balance) == wrap_amount

        return weth_balance


@pytest.fixture(scope="module")
def position_manager_helpers():

    def _instantiate_position_manager_helpers(web3, position_manager, position_manager_abi, token_0, token_1):
        return PositionManagerHelpers(
            web3=web3,
            position_manager=position_manager,
            position_manager_abi=position_manager_abi,
            token_0=token_0,
            token_1=token_1
        )
    return _instantiate_position_manager_helpers