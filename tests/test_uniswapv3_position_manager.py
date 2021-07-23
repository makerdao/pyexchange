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
from typing import List

import pkg_resources
import pytest
import unittest

from fxpmath import Fxp
from enum import Enum
from web3 import Web3, HTTPProvider

from pyexchange.uniswapv3 import PositionManager, SwapRouter
from pyexchange.uniswapv3_constants import FEES, TICK_SPACING, TRADE_TYPE, MIN_TICK
from pyexchange.uniswapv3_calldata_params import BurnParams, CollectParams, DecreaseLiquidityParams, MintParams, \
    ExactOutputSingleParams, ExactInputSingleParams, MulticallParams
from pyexchange.uniswapv3_entities import Pool, Position, Route, Trade, CurrencyAmount, Fraction, PriceFraction
from pyexchange.uniswapv3_math import encodeSqrtRatioX96, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, Tick
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.gas import FixedGasPrice
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token


# TODO: update to use snake case
# TODO: generalize / split out tests for SwapRouter?
class TestUniswapV3PositionManager(Contract):

    """ Deployment docs available here: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/deploys.md """

    UniswapV3Factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV3Factory.abi')['abi']
    UniswapV3Factory_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV3Factory.bin')
    NFTDescriptor_abi = Contract._load_abi(__name__, '../pyexchange/abi/NFTDescriptor.abi')['abi']
    NFTDescriptor_bin = Contract._load_bin(__name__, '../pyexchange/abi/NFTDescriptor.bin')
    weth_abi = Contract._load_abi(__name__, '../pyexchange/abi/WETH.abi')
    weth_bin = Contract._load_bin(__name__, '../pyexchange/abi/WETH.bin')
    NonfungiblePositionManager_abi = Contract._load_abi(__name__, '../pyexchange/abi/NonfungiblePositionManager.abi')['abi']
    NonfungiblePositionManager_bin = Contract._load_bin(__name__, '../pyexchange/abi/NonfungiblePositionManager.bin')
    SwapRouter_abi = Contract._load_abi(__name__, '../pyexchange/abi/SwapRouter.abi')['abi']
    SwapRouter_bin = Contract._load_bin(__name__, '../pyexchange/abi/SwapRouter.bin')
    UniswapV3TickLens_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV3TickLens.abi')['abi']
    UniswapV3TickLens_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV3TickLens.bin')
    Quoter_abi = Contract._load_abi(__name__, '../pyexchange/abi/Quoter.abi')['abi']
    Quoter_bin = Contract._load_bin(__name__, '../pyexchange/abi/Quoter.bin')

    def setup_class(self):
        time.sleep(10)
        # Use Ganache docker container
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555", request_kwargs={'timeout': 60}))
        self.web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
        register_private_key(self.web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")

        self.our_address = Address(self.web3.eth.defaultAccount)

        # constructor args for nonfungiblePositionManager
        self.factory_address: Address = self._deploy(self.web3, self.UniswapV3Factory_abi, self.UniswapV3Factory_bin, [])
        self.weth_address: Address = self._deploy(self.web3, self.weth_abi, self.weth_bin, [])
        self.token_descriptor_address: Address = self._deploy(self.web3, self.NFTDescriptor_abi, self.NFTDescriptor_bin, [])

        self.nonfungiblePositionManager_address = self._deploy(self.web3, self.NonfungiblePositionManager_abi, self.NonfungiblePositionManager_bin, [self.factory_address.address, self.weth_address.address, self.token_descriptor_address.address])

        self.tick_lens_address = self._deploy(self.web3, self.UniswapV3TickLens_abi, self.UniswapV3TickLens_bin, [])
        self.position_manager = PositionManager(self.web3, self.nonfungiblePositionManager_address, self.factory_address, self.tick_lens_address, self.weth_address)

        self.swap_router_address = self._deploy(self.web3, self.SwapRouter_abi, self.SwapRouter_bin, [self.factory_address.address, self.weth_address.address])
        self.quoter_address = self._deploy(self.web3, self.Quoter_abi, self.Quoter_bin, [self.factory_address.address, self.weth_address.address])

        self.swap_router = SwapRouter(self.web3, self.swap_router_address, self.quoter_address)

        ## Useful for debugging failing transactions
        logger = logging.getLogger('eth')
        logger.setLevel(8)
        Transact.gas_estimate_for_bad_txs = 210000

    def setup_method(self):
        self.ds_dai = DSToken.deploy(self.web3, 'DAI')
        self.ds_usdc = DSToken.deploy(self.web3, 'USDC')
        self.token_dai = Token("DAI", self.ds_dai.address, 18)
        self.token_usdc = Token("USDC", self.ds_usdc.address, 6)
        self.token_weth = Token("WETH", self.weth_address, 18)

        self.position_manager.approve(self.token_dai)
        self.position_manager.approve(self.token_usdc)
        self.position_manager.approve(self.token_weth)
        self.swap_router.approve(self.token_dai)
        self.swap_router.approve(self.token_usdc)
        self.swap_router.approve(self.token_weth)

        # TODO: normalize amounts for decimals
        dai_balance = Wad.from_number(10000)
        usdc_balance = Wad.from_number(10000)

        self.ds_dai.mint(dai_balance).transact(from_address=self.our_address)
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(usdc_balance)).transact(from_address=self.our_address)

    # TODO: is sqrt_price_x96 from mint amounts nedded for pool creation, or can 0 be used instead?
    def create_and_initialize_usdcdai_pool(self, starting_sqrt_price_x96: int) -> Pool:

        # TODO: best way to do this?
        token_0, token_1 = self.position_manager._set_address_order(self.token_dai, self.token_usdc)
        create_pool_receipt = self.position_manager.create_pool(token_0, token_1, FEES.LOW.value, starting_sqrt_price_x96).transact()

        assert create_pool_receipt is not None and create_pool_receipt.successful
        liquidity = 0 # liquidity is 0 upon initalization
        # # tick_current = get_tick_at_sqrt_ratio(starting_square_root_ratio_x96)
        # TODO: offset tick_current based upon expected pool ticks used in test
        tick_current = 0

        # TODO: dynamically retrieve token ordering based on comparison operator
        pool = Pool(
            token_0,
            token_1,
            FEES.LOW.value,
            starting_sqrt_price_x96,
            liquidity,
            tick_current,
            []
        )
        return pool

    def get_starting_sqrt_ratio(self, amount_0, amount_1) -> int:
        return encodeSqrtRatioX96(amount_1, amount_0)

    def generate_mint_usdcdai_params(self, pool: Pool) -> MintParams:
        amount_0 = 100 * 10 ** 6
        amount_1 = 100 * 10 ** 18
        # self.mint_tokens(Wad.from_number(amount_0), Wad.from_number(amount_1))

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

        deadline = int(time.time()) + 1000
        position = Position(pool, -10, 10, 1)
        slippage_tolerance = Fraction(20, 100)
        recipient = self.our_address

        mint_params = MintParams(self.web3, self.NonfungiblePositionManager_abi, position, recipient, slippage_tolerance, deadline)
        return mint_params

    # TODO: tie newly minted underlying assets to minted amount
    def test_mint_token_pool(self, position_manager_helpers):
        position_manager_helper = position_manager_helpers(self.web3, self.position_manager, self.NonfungiblePositionManager_abi, self.token_dai, self.token_usdc)
        pool = position_manager_helper.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1), FEES.LOW.value)

        mint_params = position_manager_helper.generate_mint_params(pool, Position(pool, -10, 10, 10), self.our_address, Fraction(20, 100))

        gas_price = FixedGasPrice(gas_price=20000000000000000)
        gas_limit = 6021975
        mint_receipt = self.position_manager.mint(mint_params).transact(gas_price=gas_price)
        assert mint_receipt is not None and mint_receipt.successful

    def test_mint_eth_token_pool(self, position_manager_helpers):
        # TODO: base pricing on token order
        # pool = self.create_and_initialize_ethdai_pool(self.get_starting_sqrt_ratio(1900, 1))

        position_manager_helper = position_manager_helpers(self.web3, self.position_manager, self.NonfungiblePositionManager_abi, self.token_weth, self.token_dai)

        pool = position_manager_helper.create_and_initialize_pool(self.get_starting_sqrt_ratio(1900, 1), FEES.MEDIUM.value)

        position_manager_helper.wrap_eth(Wad.from_number(1), self.our_address)

        mint_params = position_manager_helper.generate_mint_params(pool, Position(pool, -60, 60, 10), self.our_address, Fraction(20, 100))

        mint_receipt = self.position_manager.mint(mint_params).transact()
        assert mint_receipt is not None and mint_receipt.successful

    def test_get_position_from_id(self):
        # create and intialize pool
        pool = self.create_and_initialize_usdcdai_pool(self.get_starting_sqrt_ratio(1, 1))

        mint_params = self.generate_mint_usdcdai_params(pool)

        mint_receipt = self.position_manager.mint(mint_params).transact()
        assert mint_receipt is not None and mint_receipt.successful

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id

        position = self.position_manager.positions(token_id)

        assert isinstance(position, Position)

        # check that position price matches minted position expectations
        position_price = self.position_manager.price_position(token_id, 1)
        assert position_price == Wad(4002000400040001800000)

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

    def test_burn(self):
        # create and intialize pool
        pool = self.create_and_initialize_usdcdai_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_usdcdai_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id
        liquidity = mint_receipt.result[0].liquidity
        amount_0 = mint_receipt.result[0].amount_0
        amount_1 = mint_receipt.result[0].amount_1

        # decrease liquidity - remove all minted liquidity
        decrease_liquidity_params = DecreaseLiquidityParams(self.web3, self.NonfungiblePositionManager_abi, token_id, liquidity, amount_0 - 1, amount_1 - 1, None)
        decrease_liquidity_receipt = self.position_manager.decrease_liquidity(decrease_liquidity_params).transact()

        assert decrease_liquidity_receipt is not None and decrease_liquidity_receipt.successful

        # burn previously created position
        burn_params = BurnParams(self.web3, self.NonfungiblePositionManager_abi, token_id)
        burn_receipt = self.position_manager.burn(burn_params).transact()

        assert burn_receipt is not None and burn_receipt.successful

    # multicall(decreaseLiquidity, burn)
    def test_multicall_burn(self):
        # create and intialize pool
        pool = self.create_and_initialize_usdcdai_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_usdcdai_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id
        liquidity = mint_receipt.result[0].liquidity
        amount_0 = mint_receipt.result[0].amount_0
        amount_1 = mint_receipt.result[0].amount_1

        # decrease liquidity - remove all minted liquidity
        decrease_liquidity_params = DecreaseLiquidityParams(self.web3, self.NonfungiblePositionManager_abi, token_id, liquidity, amount_0 - 1, amount_1 - 1, None)

        # burn position following liquidity removal
        burn_params = BurnParams(self.web3, self.NonfungiblePositionManager_abi, token_id)

        multicall_calldata = [
            decrease_liquidity_params.calldata.value,
            burn_params.calldata.value
        ]

        multicall_params = MulticallParams(self.web3, self.NonfungiblePositionManager_abi, multicall_calldata).calldata.value
        multicall_receipt = self.position_manager.multicall([multicall_params]).transact()
        # print("burn multicall calldata", decrease_liquidity_params.calldata, burn_params.calldata)
        # multicall_receipt = self.position_manager.multicall(multicall_calldata).transact(from_address=self.our_address)
        assert multicall_receipt is not None and multicall_receipt.successful

    # TODO: add support for swaps to generate fees
    def test_collect_exact_output_swap(self, position_manager_helpers):
        # create and intialize pool
        position_manager_helper = position_manager_helpers(self.web3, self.position_manager, self.NonfungiblePositionManager_abi, self.token_dai, self.token_usdc)
        pool = position_manager_helper.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1), FEES.LOW.value)

        # mint initial liquidity
        mint_params = position_manager_helper.generate_mint_params(pool, Position(pool, -10, 10, 1000), self.our_address, Fraction(20, 100))
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id
        # TODO: need to get a new pool entity that reflects the new ticks[] reflecting the added liquidity
        minted_position = self.position_manager.positions(token_id)

        # execute swaps against the pool to generate fees
        amount_out = 10
        slippage_tolerance = Fraction(20, 100) # equivalent to 0.2
        recipient = self.our_address
        # recipient = Address("0x253De0f274677334eC814Fc99794C3F228de6fF3")
        deadline = int(time.time() + 10000)
        # price_limit = 0

        # TODO: figure out why self.token_usdc != pool.token_usdc
        # route = Route([minted_position.pool], self.token_usdc, self.token_dai)
        # trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(self.token_dai, amount_out), TRADE_TYPE.EXACT_OUTPUT_SINGLE.value)
        route = Route([minted_position.pool], minted_position.pool.token_0, minted_position.pool.token_1)
        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(minted_position.pool.token_1, amount_out), TRADE_TYPE.EXACT_OUTPUT_SINGLE.value)

        # TODO: fix this calculation
        max_amount_in = trade.maximum_amount_in(slippage_tolerance).quotient()
        trade_amount_in = trade.input_amount.quotient()
        print("alts", max_amount_in, trade_amount_in)
        sqrt_price_limit = 100000000000000000000000
        amount_in = self.swap_router.quote_exact_output_single(pool.token_0, pool.token_1, pool.fee, amount_out, sqrt_price_limit)

        # amount_in = trade.input_amount.quotient()

        exact_output_single_params = ExactOutputSingleParams(self.web3, self.SwapRouter_abi, trade.route.token_path[0], trade.route.token_path[1], trade.route.pools[0].fee, recipient, deadline, amount_out, amount_in, sqrt_price_limit)
        swap = self.swap_router.swap_exact_output_single(exact_output_single_params).transact()
        assert swap is not None and swap.successful

        position_amount_0, position_amount_1 = self.position_manager.get_position_reserves(token_id)

        # collect fees from position
        collect_params = CollectParams(self.web3, self.NonfungiblePositionManager_abi, token_id, self.our_address, int(position_amount_0), int(position_amount_1))
        collect_receipt = self.position_manager.collect(collect_params).transact()

        assert collect_receipt is not None and collect_receipt.successful

    def test_collect_exact_input_swap(self):
        # create and intialize pool
        pool = self.create_and_initialize_usdcdai_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_usdcdai_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id

        position_amount_0 = self.position_manager.get_position_info(token_id)[10]
        position_amount_1 = self.position_manager.get_position_info(token_id)[11]
        print("before swap, amounts", position_amount_0, position_amount_1)
        # TODO: need to get a new pool entity that reflects the new ticks[] reflecting the added liquidity
        minted_position = self.position_manager.positions(token_id)

        amount_in = 1
        recipient = self.our_address
        deadline = int(time.time() + 10000)
        price_limit = 0

        route = Route([minted_position.pool], minted_position.pool.token_0, minted_position.pool.token_1)
        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(minted_position.pool.token_0, amount_in),
                                 TRADE_TYPE.EXACT_INPUT_SINGLE.value)

        amount_out = trade.output_amount.quotient()
        exact_input_single_params = ExactInputSingleParams(self.web3, self.SwapRouter_abi, trade.route.token_path[0], trade.route.token_path[1], trade.route.pools[0].fee, recipient, deadline, amount_in, amount_out, price_limit)

        swap = self.swap_router.swap_exact_input_single(exact_input_single_params).transact()
        assert swap is not None and swap.successful

        # position_amount_0 = self.position_manager.get_position_info(token_id)[10]
        # position_amount_1 = self.position_manager.get_position_info(token_id)[11]
        position_amount_0 = 0
        position_amount_1 = 1

        # collect fees from position
        collect_params = CollectParams(self.web3, self.NonfungiblePositionManager_abi, token_id, self.our_address, position_amount_0, position_amount_1)
        collect_receipt = self.position_manager.collect(collect_params).transact()

        assert collect_receipt is not None and collect_receipt.successful

        post_collect_position = self.position_manager.positions(token_id)
        print("post collect", post_collect_position)
        assert False

    # TODO: multicall[collect, decreaseLiquidity, burn]
    def test_collect_and_burn(self):
        pass

