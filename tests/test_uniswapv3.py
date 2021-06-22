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

from fxpmath import Fxp
from enum import Enum
from web3 import Web3, HTTPProvider

from pyexchange.uniswapv3 import PositionManager
from pyexchange.uniswapv3_entities import Pool, Position, BurnParams, CollectParams, MintParams
from pyexchange.uniswapv3_math import encodeSqrtRatioX96, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio
from pymaker import Address, Contract, Receipt, Transact
from pymaker.deployment import deploy_contract
from pymaker.keys import register_keys, register_private_key
from pymaker.gas import FixedGasPrice
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
        time.sleep(10)
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

    # TODO: retrieve log events from create pool event
    # TODO: is sqrt_price_x96 from mint amounts nedded for pool creation, or can 0 be used instead?
    def create_and_initialize_pool(self, starting_sqrt_price_x96: int) -> Pool:
        self.position_manager.create_pool(self.token_dai, self.token_usdc, FEES.LOW.value, starting_sqrt_price_x96).transact()

        liquidity = 0 # liquidity is 0 upon initalization
        # # tick_current = get_tick_at_sqrt_ratio(starting_square_root_ratio_x96)
        # TODO: offset tick_current based upon expected pool ticks used in test
        tick_current = 0

        pool = Pool(
            self.token_dai,
            self.token_usdc,
            FEES.LOW.value,
            starting_sqrt_price_x96,
            liquidity,
            tick_current,
            []
        )
        return pool

    def get_starting_sqrt_ratio(self, amount_0, amount_1) -> int:
        return encodeSqrtRatioX96(amount_1, amount_0)

    def generate_mint_params(self, pool: Pool) -> MintParams:
        amount_0 = 100 * 10 ** 6
        amount_1 = 100 * 10 ** 18
        self.mint_tokens(Wad.from_number(amount_0), Wad.from_number(amount_1))

        # starting_square_root_ratio_x96 = self.get_starting_sqrt_ratio(amount_0, amount_1)
        # liquidity = 0 # liquidity is 0 upon initalization
        # # TODO: if using formula to establish starting sqrt_ratio need to corresponding offest tick lower and higher
        # # tick_current = get_tick_at_sqrt_ratio(starting_square_root_ratio_x96)
        # tick_current = 0
        #
        # pool = Pool(
        #     self.token_dai,
        #     self.token_usdc,
        #     FEES.LOW.value,
        #     starting_square_root_ratio_x96,
        #     liquidity,
        #     tick_current,
        #     []
        # )

        position = Position(pool, -10, 10, 1)

        recipient = self.our_address
        mint_params = self.position_manager.generate_mint_params(self.web3, position, recipient, 0.2)
        return mint_params

    # def test_create_and_initalize_pool(self):
    #     new_pool_address = self.create_and_initialize_pool()
    #
    #     assert isinstance(new_pool_address, Address)
    #
    # def test_generate_mint_params(self):
    #     mint_params = self.generate_mint_params()
    #     assert isinstance(mint_params, MintParams)

    # TODO: tie newly minted underlying assets to minted amount
    def test_mint(self):
        amount_0 = 100 * 10 ** 6
        amount_1 = 100 * 10 ** 18
        # create and intialize pool
        # pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(amount_0, amount_1))
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        mint_params = self.generate_mint_params(pool)

        gas_price = FixedGasPrice(gas_price=20000000000000000)
        gas_limit = 6021975
        mint_receipt = self.position_manager.mint(mint_params).transact(gas_price=gas_price)
        print(mint_receipt)
        assert mint_receipt is not None and mint_receipt.successful

    # https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/base/Multicall.sol
    # def test_multicall_mint(self):
    #     amount_0 = 100 * 10 ** 6
    #     amount_1 = 100 * 10 ** 18
    #     # create and intialize pool
    #     pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(amount_0, amount_1))
    #     # # create and intialize pool
    #
    #     multicall_mint_params = self.generate_mint_params(pool)
    #     multicall_mint_receipt = self.position_manager.multicall([multicall_mint_params.calldata.as_bytes()]).transact()
    #     assert multicall_mint_receipt is not None
    #
    #     # check token balance
    #     assert self.position_manager.balance_of()

    # def test_position_manager_deployment(self):
    #     test_call = self.nonfungiblePositionManager_contract.functions.DOMAIN_SEPARATOR().call()
    #     print(test_call)
    #     assert test_call is True

    # TODO: multicall (decreaseLiquidity, burn)
    def test_burn(self):
        # create and intialize pool
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id #['token_id']

        # burn previously created position
        burn_params = BurnParams(self.web3, token_id)
        burn_receipt = self.position_manager.burn(burn_params).transact()

        assert burn_receipt is not None and burn_receipt.successful

    # TODO: add support for swaps to generate fees
    def test_collect(self):
        # create and intialize pool
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0]['token_id']

        # execute swaps against the pool to generate fees

        # collect fees from position
        collect_params = CollectParams(self.web3, token_id)
        collect_receipt = self.position_manager.collect(collect_params).transact()

        assert collect_receipt is not None and collect_receipt.successful

    def test_positions(self):
        pass
