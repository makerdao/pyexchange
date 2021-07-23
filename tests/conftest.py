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


# @pytest.fixture(scope="session")
# def web3() -> Web3:
#     # for local dockerized parity testchain
#     web3 = web3_via_http("http://0.0.0.0:8555")
#     web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
#     register_private_key(web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")
#     return web3

# @pytest.fixture()
# def uniswapv3_contract_artifacts() -> set:
#     UniswapV3Factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV3Factory.abi')['abi']
#     UniswapV3Factory_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV3Factory.bin')
#     NFTDescriptor_abi = Contract._load_abi(__name__, '../pyexchange/abi/NFTDescriptor.abi')['abi']
#     NFTDescriptor_bin = Contract._load_bin(__name__, '../pyexchange/abi/NFTDescriptor.bin')
#     weth_abi = Contract._load_abi(__name__, '../pyexchange/abi/WETH.abi')
#     weth_bin = Contract._load_bin(__name__, '../pyexchange/abi/WETH.bin')
#     NonfungiblePositionManager_abi = Contract._load_abi(__name__, '../pyexchange/abi/NonfungiblePositionManager.abi')['abi']
#     NonfungiblePositionManager_bin = Contract._load_bin(__name__, '../pyexchange/abi/NonfungiblePositionManager.bin')
#     SwapRouter_abi = Contract._load_abi(__name__, '../pyexchange/abi/SwapRouter.abi')['abi']
#     SwapRouter_bin = Contract._load_abi(__name__, '../pyexchange/abi/SwapRouter.bin')
#
#     return {
#         UniswapV3Factory_abi,
#         UniswapV3Factory_bin,
#         NFTDescriptor_abi,
#         NFTDescriptor_bin,
#         weth_abi,
#         weth_bin,
#         NonfungiblePositionManager_abi,
#         NonfungiblePositionManager_bin,
#         SwapRouter_abi,
#         SwapRouter_bin
#     }

# @pytest.fixture()
# def deploy_uniswapv3_position_manager(web3, uniswapv3_contract_artifacts) -> PositionManager:
#     self.nonfungiblePositionManager_address = Contract._deploy(web3, self.NonfungiblePositionManager_abi,
#                                                            self.NonfungiblePositionManager_bin,
#                                                            [self.factory_address.address, self.weth_address.address,
#                                                             self.token_descriptor_address.address])
#
#     # TODO: use PositionManager.nft_position_manager_contract instead
#     self.nonfungiblePositionManager_contract = self._get_contract(self.web3, self.NonfungiblePositionManager_abi,
#                                                                   self.nonfungiblePositionManager_address)
#     self.position_manager = PositionManager(self.web3, self.nonfungiblePositionManager_address, self.factory_address)
#     return PositionManager()
#
# @pytest.fixture()
# def deploy_uniswapv3_swap_router(web3, uniswapv3_contract_artifacts) -> SwapRouter:
#     return SwapRouter()


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

        liquidity = 0  # liquidity is 0 upon initalization

        tick_current = 0

        # TODO: dynamically retrieve token ordering based on comparison operator
        pool = Pool(
            token_0,
            token_1,
            fee,
            starting_sqrt_price_x96,
            liquidity,
            tick_current,
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