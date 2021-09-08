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
import time
import logging
import requests

import pkg_resources
import pytest
import unittest

from web3 import Web3, HTTPProvider

from pyexchange.uniswapv3 import PositionManager, SwapRouter
from pyexchange.uniswapv3_constants import FEES, TICK_SPACING, TRADE_TYPE, MAX_TICK, MAX_SQRT_RATIO, MIN_TICK, \
    MIN_SQRT_RATIO, Q96, MAX_UINT128
from pyexchange.uniswapv3_calldata_params import BurnParams, CollectParams, DecreaseLiquidityParams, MintParams, \
    ExactOutputSingleParams, ExactInputSingleParams, MulticallParams
from pyexchange.uniswapv3_entities import Pool, Position, Route, Trade, CurrencyAmount, Fraction, PriceFraction
from pyexchange.uniswapv3_math import encodeSqrtRatioX96, isqrt, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, Tick, \
    SqrtPriceMath
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.gas import FixedGasPrice
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token


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
        # Use Ganache docker container
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555", request_kwargs={'timeout': 60}))
        self.web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
        register_private_key(self.web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")

        self.our_address = Address(self.web3.eth.defaultAccount)

        # take snapshot of ganache EVM state at genesis
        session = requests.Session()
        method = 'evm_snapshot'
        params = []
        payload = {"jsonrpc": "2.0",
                   "method": method,
                   "params": params,
                   "id": 1}
        headers = {'Content-type': 'application/json'}
        response = session.post('http://0.0.0.0:8555', json=payload, headers=headers)

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

        dai_balance = Wad.from_number(10000000)
        usdc_balance = Wad.from_number(10000000)

        self.ds_dai.mint(dai_balance).transact(from_address=self.our_address)
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(usdc_balance)).transact(from_address=self.our_address)

    def create_and_initialize_usdcdai_pool(self, starting_sqrt_price_x96: int) -> Pool:

        token_0, token_1 = self.position_manager._set_address_order(self.token_dai, self.token_usdc)
        create_pool_receipt = self.position_manager.create_pool(token_0, token_1, FEES.LOW.value, starting_sqrt_price_x96).transact()

        assert create_pool_receipt is not None and create_pool_receipt.successful
        liquidity = 0 # liquidity is 0 upon initalization
        tick_current = create_pool_receipt.result[0].tick

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

        deadline = int(time.time()) + 1000
        position = Position(pool, -10, 10, 1)
        slippage_tolerance = Fraction(20, 100)
        recipient = self.our_address

        mint_params = MintParams(self.web3, self.NonfungiblePositionManager_abi, position, recipient, slippage_tolerance, deadline)
        return mint_params

    def test_liquidity_given_balance(self):
        """ Test liquidity and mint amount calculations """
        test_token_1 = Token("test_1", Address("0x0000000000000000000000000000000000000001"), 18)
        test_token_2 = Token("test_2", Address("0x0000000000000000000000000000000000000002"), 6)

        token_1_balance = test_token_1.unnormalize_amount(Wad.from_number(10))
        token_2_balance = test_token_2.unnormalize_amount(Wad.from_number(500))

        sqrt_price_ratio = self.get_starting_sqrt_ratio(Wad.from_number(1).value, test_token_2.unnormalize_amount(Wad.from_number(3000)).value)
        current_tick = get_tick_at_sqrt_ratio(sqrt_price_ratio)
        ticks = []
        test_pool = Pool(test_token_1, test_token_2, FEES.MEDIUM.value, sqrt_price_ratio, 0, current_tick, ticks)

        tick_lower = current_tick - TICK_SPACING.MEDIUM.value * 5
        tick_upper = current_tick + TICK_SPACING.MEDIUM.value * 7
        rounded_tick_lower = Tick.nearest_usable_tick(tick_lower, TICK_SPACING.MEDIUM.value)
        rounded_tick_upper = Tick.nearest_usable_tick(tick_upper, TICK_SPACING.MEDIUM.value)
        calculated_position = Position.from_amounts(test_pool, rounded_tick_lower, rounded_tick_upper, token_1_balance.value, token_2_balance.value, False)

        test_liquidity = calculated_position.liquidity
        assert test_liquidity == 252860870269028

        test_position = Position(test_pool, rounded_tick_lower, rounded_tick_upper, test_liquidity)

        amount_0, amount_1 = test_position.mint_amounts()
        assert amount_0 == 95107120950731527
        assert amount_1 == 208677042

    def test_mint_token_pool_low_price_and_slippage(self):
        """ Test minting a position for a pool that is a small fraction """
        test_token_1 = Token("test_1", Address("0x0000000000000000000000000000000000000001"), 18)
        test_token_2 = Token("test_2", Address("0x0000000000000000000000000000000000000002"), 18)

        token_1_balance = Wad.from_number(10)
        token_2_balance = Wad.from_number(100)

        # sqrt_price_ratio = self.get_starting_sqrt_ratio(3000, 1)
        sqrt_price_ratio = self.get_starting_sqrt_ratio(Wad.from_number(3000).value, Wad.from_number(1).value)
        current_tick = get_tick_at_sqrt_ratio(sqrt_price_ratio)
        ticks = []
        test_pool = Pool(test_token_1, test_token_2, FEES.MEDIUM.value, sqrt_price_ratio, 0, current_tick, ticks)

        # set Position.from_amounts() params
        tick_lower = current_tick - TICK_SPACING.MEDIUM.value * 5
        tick_upper = current_tick + TICK_SPACING.MEDIUM.value * 7
        rounded_tick_lower = Tick.nearest_usable_tick(tick_lower, TICK_SPACING.MEDIUM.value)
        rounded_tick_upper = Tick.nearest_usable_tick(tick_upper, TICK_SPACING.MEDIUM.value)
        calculated_position = Position.from_amounts(test_pool, rounded_tick_lower, rounded_tick_upper, token_1_balance.value, token_2_balance.value, False)

        test_liquidity = calculated_position.liquidity

        test_position = Position(test_pool, rounded_tick_lower, rounded_tick_upper, test_liquidity)

        amount_0, amount_1 = test_position.mint_amounts()

        slippage_tolerance = Fraction(2, 100)
        amount_0_min, amount_1_min = test_position.mint_amounts_with_slippage(slippage_tolerance)

        # check that mint amounts will pass periphery contract assertions
        assert amount_0_min > 0 and amount_1_min > 0
        assert amount_0_min < amount_0 and amount_1_min < amount_1

    def test_should_mint_with_nonstandard_decimals(self):
        """ mint a position with one of the tokens having nonstandard decimals.
            Verify that the positions price and minted amounts accounts for decimals.
        """
        test_token_1 = Token("test_1", Address("0x0000000000000000000000000000000000000001"), 18)
        test_token_2 = Token("test_2", Address("0x0000000000000000000000000000000000000002"), 6)

        # instantiate test pool
        # sqrt_price_ratio = self.get_starting_sqrt_ratio(Wad.from_number(1).value, Wad.from_number(3500).value)
        sqrt_price_ratio = self.get_starting_sqrt_ratio(1, 3500)
        current_tick = get_tick_at_sqrt_ratio(sqrt_price_ratio)
        ticks = []
        test_pool = Pool(test_token_1, test_token_2, FEES.MEDIUM.value, sqrt_price_ratio, 0, current_tick, ticks)

        # based upon current price (expressed in token1/token0), determine the tick to mint the position at
        tick_spacing = TICK_SPACING.MEDIUM.value
        desired_price = PriceFraction(test_token_1, test_token_2, 1, 3500)
        desired_tick = PriceFraction.get_tick_at_price(desired_price)

        # identify upper and lower tick bounds for the position
        desired_lower_tick = Tick.nearest_usable_tick(desired_tick - tick_spacing * 5, tick_spacing)
        desired_upper_tick = Tick.nearest_usable_tick(desired_tick + tick_spacing * 7, tick_spacing)

        # calculate amount to add for each position.
        ## since test_token_2 has 6 decimals, we must unnormalize the Wad amount from 18 -> 6
        token_1_balance = Wad.from_number(10)
        token_2_balance = Wad.from_number(100)

        token_1_to_add = test_token_1.unnormalize_amount(token_1_balance).value
        token_2_to_add = test_token_2.unnormalize_amount(token_2_balance).value
        # token_1_to_add = token_1_balance.value
        # token_2_to_add = token_2_balance.value

        calculated_position = Position.from_amounts(test_pool, desired_lower_tick, desired_upper_tick, token_1_to_add, token_2_to_add, False)

        amount_0, amount_1 = calculated_position.mint_amounts()

        slippage_tolerance = Fraction(2, 100)
        amount_0_min, amount_1_min = calculated_position.mint_amounts_with_slippage(slippage_tolerance)

        # check that mint amounts will pass periphery contract assertions
        assert amount_0 > 0 and amount_1 > 0
        assert amount_0_min > 0 and amount_1_min > 0
        assert amount_0_min < amount_0 and amount_1_min < amount_1

        # assume pool.tick_current < desired_upper_tick
        expected_amount_0 = SqrtPriceMath.get_amount_0_delta(test_pool.square_root_ratio_x96, get_sqrt_ratio_at_tick(desired_upper_tick), calculated_position.liquidity, True)
        expected_amount_1 = SqrtPriceMath.get_amount_1_delta(get_sqrt_ratio_at_tick(desired_lower_tick), test_pool.square_root_ratio_x96, calculated_position.liquidity, True)

        assert amount_0 == expected_amount_0
        assert amount_1 == expected_amount_1

        # get amounts from liquidity
        price_lower_tick = pow(1.0001, calculated_position.tick_lower)
        price_upper_tick = pow(1.0001, calculated_position.tick_upper)

        assert price_lower_tick < 3500 < price_upper_tick

        position_token_0 = calculated_position.liquidity / math.sqrt(price_upper_tick)
        position_token_1 = calculated_position.liquidity * math.sqrt(price_lower_tick)

        # compare original sqrt_price_ratio_x96 to the ratio determined by liquidity to mint
        assert str(sqrt_price_ratio)[:2] == str(encodeSqrtRatioX96(int(position_token_1), int(position_token_0)))[:2]
        assert sqrt_price_ratio // Q96 == encodeSqrtRatioX96(int(position_token_1), int(position_token_0)) // (2 ** 96)

    def test_mint_token_pool(self, position_manager_helpers):
        """ Integration test to mint a pool with two ERC20 tokens """
        # create pool
        position_manager_helper = position_manager_helpers(self.web3, self.position_manager, self.NonfungiblePositionManager_abi, self.token_dai, self.token_usdc)
        pool = position_manager_helper.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1), FEES.LOW.value)

        # generate MintParam
        mint_params = position_manager_helper.generate_mint_params(pool, Position(pool, -10, 10, 10), self.our_address, Fraction(1, 100))

        # mint new position
        gas_price = FixedGasPrice(gas_price=20000000000000000)
        mint_receipt = self.position_manager.mint(mint_params).transact(gas_price=gas_price)
        assert mint_receipt is not None and mint_receipt.successful

    def test_mint_eth_token_pool(self, position_manager_helpers):
        """ Integration test to mint a pool where one side is WETH """
        position_manager_helper = position_manager_helpers(self.web3, self.position_manager, self.NonfungiblePositionManager_abi, self.token_weth, self.token_dai)

        # starting pool price for weth-dai 1900
        pool = position_manager_helper.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1900), FEES.MEDIUM.value)

        # wrap ETH into WETH as UniV3 only works with ERC20 tokens
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

        position = self.position_manager.positions(token_id, pool.token_0, pool.token_1)

        assert isinstance(position, Position)

        # check that position price matches minted position expectations
        position_price = self.position_manager.price_position(token_id, 1)
        assert position_price == Wad(4002000400040001800000)

    # TODO: implement permit
    # https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/base/Multicall.sol
    # def test_multicall_permit_mint(self):
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
        """ Integration test of minting a new position, removing liquidity from it, then burning the position """
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
        """ Integration test of minting a new position, removing liquidity from it, then burning the position.
            All in a single multicall transaction
        """
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

        # collect encoded params into a list
        multicall_calldata = [
            decrease_liquidity_params.calldata.value,
            burn_params.calldata.value
        ]

        multicall_params = MulticallParams(self.web3, self.NonfungiblePositionManager_abi, multicall_calldata).calldata.value
        multicall_receipt = self.position_manager.multicall([multicall_params]).transact()
        assert multicall_receipt is not None and multicall_receipt.successful

    def test_collect_exact_output_swap(self, position_manager_helpers):
        """ Integration test of minting a new position, executing an ExactOutput swap against the positions liquidity
            to ensure fees are available, and then collecting those fees.
        """
        # create and intialize pool
        position_manager_helper = position_manager_helpers(self.web3, self.position_manager, self.NonfungiblePositionManager_abi, self.token_dai, self.token_usdc)
        pool = position_manager_helper.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1), FEES.LOW.value)

        # mint initial liquidity
        mint_params = position_manager_helper.generate_mint_params(pool, Position(pool, -10, 10, 100000000000000), self.our_address, Fraction(20, 100))
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id
        minted_position = self.position_manager.positions(token_id, pool.token_0, pool.token_1)

        # execute swaps against the pool to generate fees
        amount_out = Wad.from_number(10)
        slippage_tolerance = Fraction(20, 100) # equivalent to 0.2
        recipient = self.our_address
        deadline = int(time.time() + 10000)

        # Build Route and Trade entities that can be used to determine amount_in
        route = Route([minted_position.pool], minted_position.pool.token_0, minted_position.pool.token_1)
        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(minted_position.pool.token_1, amount_out.value), TRADE_TYPE.EXACT_OUTPUT_SINGLE.value)

        max_amount_in = trade.maximum_amount_in(slippage_tolerance).quotient()
        trade_amount_in = trade.input_amount.quotient()
        print("alts", max_amount_in, trade_amount_in)
        sqrt_price_limit = 100000000000000000000000
        amount_in = self.swap_router.quote_exact_output_single(pool.token_0, pool.token_1, pool.fee, amount_out.value, sqrt_price_limit)

        # amount_in = trade.input_amount.quotient()

        # Instantiate ExactOutputSingleParams that will be used to generate fees
        exact_output_single_params = ExactOutputSingleParams(self.web3, self.SwapRouter_abi, trade.route.token_path[0], trade.route.token_path[1], trade.route.pools[0].fee, recipient, deadline, amount_out.value, amount_in, sqrt_price_limit)
        swap = self.swap_router.swap_exact_output_single(exact_output_single_params).transact()
        assert swap is not None and swap.successful

        position_amount_0, position_amount_1 = self.position_manager.get_position_reserves(token_id)

        # collect fees from position
        collect_params = CollectParams(self.web3, self.NonfungiblePositionManager_abi, token_id, self.our_address, int(position_amount_0), int(position_amount_1))
        collect_receipt = self.position_manager.collect(collect_params).transact()

        assert collect_receipt is not None and collect_receipt.successful

    def test_collect_exact_input_swap(self):
        """ Integration test of minting a new position, executing an ExactInput swap against the positions liquidity
            to ensure fees are available, and then collecting those fees.
        """
        # create and intialize pool
        pool = self.create_and_initialize_usdcdai_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_usdcdai_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id

        # instantiate a Position object from the token_id
        minted_position = self.position_manager.positions(token_id, pool.token_0, pool.token_1)

        amount_in = 1
        recipient = self.our_address
        deadline = int(time.time() + 10000)
        price_limit = 0

        # Build Route and Trade entities that can be used to determine amount_out
        route = Route([minted_position.pool], minted_position.pool.token_0, minted_position.pool.token_1)
        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(minted_position.pool.token_0, amount_in),
                                 TRADE_TYPE.EXACT_INPUT_SINGLE.value)

        # Instantiate ExactInputSingleParams that will be used to generate fees
        amount_out = trade.output_amount.quotient()
        exact_input_single_params = ExactInputSingleParams(self.web3, self.SwapRouter_abi, trade.route.token_path[0], trade.route.token_path[1], trade.route.pools[0].fee, recipient, deadline, amount_in, amount_out, price_limit)

        swap = self.swap_router.swap_exact_input_single(exact_input_single_params).transact()
        assert swap is not None and swap.successful

        # collect fees from position
        collect_params = CollectParams(self.web3, self.NonfungiblePositionManager_abi, token_id, self.our_address, MAX_UINT128, MAX_UINT128)
        collect_receipt = self.position_manager.collect(collect_params).transact()

        assert collect_receipt is not None and collect_receipt.successful

