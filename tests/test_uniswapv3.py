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

import json
import time
import logging
import pkg_resources
import pytest
import unittest

from enum import Enum
from web3 import Web3, HTTPProvider

from pyexchange.uniswapv3 import PositionManager
from pyexchange.uniswapv3_entities import Pool, Position, MintParams
from pyexchange.uniswapv3_math import encodeSqrtRatioX96, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio
from pymaker import Address, Contract, Receipt, Transact
from pymaker.deployment import deploy_contract
from pymaker.keys import register_keys, register_private_key
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token


# TODO: move to uniswapv3.py?
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


# TODO: update to use snake case
# TODO: generalize / split out tests for SwapRouter?
class TestUniswapV3(Contract):

    """ Deployment docs available here: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/deploys.md """

    UniswapV3Factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV3Factory.abi')['abi']
    UniswapV3Factory_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV3Factory.bin')
    NFTDescriptor_abi = Contract._load_abi(__name__, '../pyexchange/abi/NFTDescriptor.abi')['abi']
    NFTDescriptor_bin = Contract._load_bin(__name__, '../pyexchange/abi/NFTDescriptor.bin')
    weth_abi = Contract._load_abi(__name__, '../pyexchange/abi/WETH.abi')
    weth_bin = Contract._load_bin(__name__, '../pyexchange/abi/WETH.bin')
    NonfungiblePositionManager_abi = Contract._load_abi(__name__, '../pyexchange/abi/NonfungiblePositionManager.abi')['abi']
    NonfungiblePositionManager_bin = Contract._load_bin(__name__, '../pyexchange/abi/NonfungiblePositionManager.bin') 

    def setup_method(self):
        # Use Ganache docker container
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555"))
        self.web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
        register_private_key(self.web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")

        self.our_address = Address(self.web3.eth.defaultAccount)

        # constructor args for nonfungiblePositionManager
        self.factory_address: Address = self._deploy(self.web3, self.UniswapV3Factory_abi, self.UniswapV3Factory_bin, [])
        self.weth_address: Address = self._deploy(self.web3, self.weth_abi, self.weth_bin, [])
        self.token_descriptor_address: Address = self._deploy(self.web3, self.NFTDescriptor_abi, self.NFTDescriptor_bin, [])

        self.nonfungiblePositionManager_address = self._deploy(self.web3, self.NonfungiblePositionManager_abi, self.NonfungiblePositionManager_bin, [self.factory_address.address, self.weth_address.address, self.token_descriptor_address.address])

        # TODO: use PositionManager.nft_position_manager_contract instead
        self.nonfungiblePositionManager_contract = self._get_contract(self.web3, self.NonfungiblePositionManager_abi, self.nonfungiblePositionManager_address)
        self.position_manager = PositionManager(self.web3, self.nonfungiblePositionManager_address)

        self.ds_dai = DSToken.deploy(self.web3, 'DAI')
        self.ds_usdc = DSToken.deploy(self.web3, 'USDC')
        self.token_dai = Token("DAI", self.ds_dai.address, 18)
        self.token_usdc = Token("USDC", self.ds_usdc.address, 6)

        ## Useful for debugging failing transactions
        logger = logging.getLogger('eth')
        logger.setLevel(8)
        # Transact.gas_estimate_for_bad_txs = 210000

    # TODO: add support for approving for swap router
    def mint_tokens(self, token_0_mint_amount: Wad, token_1_mint_amount: Wad):
        self.ds_dai.mint(token_0_mint_amount).transact(from_address=self.our_address)
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(token_1_mint_amount)).transact(from_address=self.our_address)
        self.position_manager.approve(self.token_dai)
        self.position_manager.approve(self.token_usdc)

    def test_generate_mint_params(self):
        
        # TODO: automate and connect with args for mint_tokens
        amount_0 = 100 * 10 ** 6
        amount_1 = 100 * 10 ** 18
        starting_square_root_ratio_x96 = encodeSqrtRatioX96(amount_1, amount_0)
        liquidity = Wad(0) # liquidity is 0 upon initalization
        # tick_current = get_tick_at_sqrt_ratio(starting_square_root_ratio_x96)

        test_zero_tick = 0

        pool = Pool(
            self.token_dai,
            self.token_usdc,
            FEES.LOW.value,
            starting_square_root_ratio_x96,
            liquidity,
            test_zero_tick,
            []
        )

        position = Position(pool, 1, -10, 10)

        recipient = self.our_address
        mint_params = self.position_manager.generate_mint_params(self.web3, position, recipient, 0.0)
        assert isinstance(mint_params, MintParams)

    def test_position_manager_deployment(self):
        test_call = self.nonfungiblePositionManager_contract.functions.DOMAIN_SEPARATOR().call()
        print(test_call)
        assert test_call is True

    def test_mint(self):
        pass

    def test_positions(self):
        pass
