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
import logging
import pytest
import requests

from web3 import Web3, HTTPProvider

from pyexchange.uniswapv3 import SwapRouter, PositionManager
from pyexchange.uniswapv3_calldata_params import ExactOutputSingleParams, ExactInputParams, ExactOutputParams
from pyexchange.uniswapv3_constants import FEES, TICK_SPACING, TRADE_TYPE
from pyexchange.uniswapv3_entities import Pool, Position, Trade, CurrencyAmount, Route, Fraction
from pyexchange.uniswapv3_math import get_tick_at_sqrt_ratio
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token

from pyexchange.uniswapv3_math import encodeSqrtRatioX96, Tick


class TestUniswapV3SwapRouter(Contract):
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
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555", request_kwargs={'timeout': 10}))
        self.web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
        register_private_key(self.web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")

        self.our_address = Address(self.web3.eth.defaultAccount)

        # reset ganache EVM state to genesis
        session = requests.Session()
        method = 'evm_revert'
        params = [1]
        payload = {"jsonrpc": "2.0",
                   "method": method,
                   "params": params,
                   "id": 1}
        headers = {'Content-type': 'application/json'}
        response = session.post('http://0.0.0.0:8555', json=payload, headers=headers)
        print("revert response: ", response)

        # constructor args for SwapRouter
        self.factory_address: Address = self._deploy(self.web3, self.UniswapV3Factory_abi, self.UniswapV3Factory_bin, [])
        self.weth_address: Address = self._deploy(self.web3, self.weth_abi, self.weth_bin, [])
        self.token_descriptor_address: Address = self._deploy(self.web3, self.NFTDescriptor_abi, self.NFTDescriptor_bin, [])

        self.swap_router_address = self._deploy(self.web3, self.SwapRouter_abi, self.SwapRouter_bin, [self.factory_address.address, self.weth_address.address])
        self.nonfungiblePositionManager_address = self._deploy(self.web3, self.NonfungiblePositionManager_abi, self.NonfungiblePositionManager_bin, [self.factory_address.address, self.weth_address.address, self.token_descriptor_address.address])
        self.tick_lens_address = self._deploy(self.web3, self.UniswapV3TickLens_abi, self.UniswapV3TickLens_bin, [])
        self.quoter_address = self._deploy(self.web3, self.Quoter_abi, self.Quoter_bin, [self.factory_address.address, self.weth_address.address])

        self.position_manager = PositionManager(self.web3, self.nonfungiblePositionManager_address, self.factory_address, self.tick_lens_address, self.weth_address)
        self.swap_router = SwapRouter(self.web3, self.swap_router_address, self.quoter_address)

        ## Useful for debugging failing transactions
        logger = logging.getLogger('eth')
        logger.setLevel(8)
        # Transact.gas_estimate_for_bad_txs = 210000

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
        dai_balance = Wad.from_number(9000000000000000)
        usdc_balance = Wad.from_number(900000000000000)

        self.ds_dai.mint(dai_balance).transact(from_address=self.our_address)
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(usdc_balance)).transact(from_address=self.our_address)

    def get_starting_sqrt_ratio(self, amount_0, amount_1) -> int:
        return encodeSqrtRatioX96(amount_1, amount_0)

    def deploy_and_mint_weth_dai(self, position_manager_helpers) -> Pool:
        # deploy weth_dai pool and mint initial liquidity to swap against
        position_manager_helper_wethdai = position_manager_helpers(self.web3, self.position_manager,
                                                                   self.NonfungiblePositionManager_abi, self.token_weth,
                                                                   self.token_dai)

        starting_price = self.get_starting_sqrt_ratio(1, 1900)
        weth_dai_pool = position_manager_helper_wethdai.create_and_initialize_pool(
            starting_price, FEES.MEDIUM.value)

        # wrap weth for testing (univ3 only uses weth)
        position_manager_helper_wethdai.wrap_eth(Wad.from_number(25), self.our_address)



        tick_lower = weth_dai_pool.tick_current - TICK_SPACING.MEDIUM.value * 3
        tick_upper = weth_dai_pool.tick_current + TICK_SPACING.MEDIUM.value * 5
        rounded_tick_lower = Tick.nearest_usable_tick(tick_lower, TICK_SPACING.MEDIUM.value)
        rounded_tick_upper = Tick.nearest_usable_tick(tick_upper, TICK_SPACING.MEDIUM.value)

        # TODO: calculate liquidity at a given price, with available balances
        # current liquidity levels result in too small of a balance being minted - need to determine why higher liquidity fails price slippage check
        liquidity_to_mint = 900000000000000

        weth_dai_mint_params = position_manager_helper_wethdai.generate_mint_params(weth_dai_pool,
                                                                                    Position(weth_dai_pool, rounded_tick_lower, rounded_tick_upper,
                                                                                             9000000000000000000), self.our_address,
                                                                                    Fraction(20, 100))
        weth_dai_mint_receipt = self.position_manager.mint(weth_dai_mint_params).transact()
        assert weth_dai_mint_receipt is not None and weth_dai_mint_receipt.successful

        # mint_result = weth_dai_mint_receipt.result[0]
        # print("mint result", mint_result, mint_result.liquidity, mint_result.tick_lower, mint_result.tick_upper)
        token_id = weth_dai_mint_receipt.result[0].token_id
        print("minted_pool token_id", token_id)
        minted_position = self.position_manager.positions(token_id, weth_dai_pool.token_0, weth_dai_pool.token_1)
        print("minted weth_dai value", self.position_manager.price_position(token_id, 1900))
        return minted_position.pool

    def deploy_and_mint_dai_usdc(self, position_manager_helpers) -> Pool:
        # deploy dai_usdc pool and mint initial liquidity to swap against
        position_manager_helper_daiusdc = position_manager_helpers(self.web3, self.position_manager,
                                                                   self.NonfungiblePositionManager_abi, self.token_dai,
                                                                   self.token_usdc)

        dai_usdc_pool = position_manager_helper_daiusdc.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1),
                                                                                        FEES.LOW.value)

        liquidity_to_mint = 1000000000
        dai_usdc_mint_params = position_manager_helper_daiusdc.generate_mint_params(dai_usdc_pool,
                                                                                    Position(dai_usdc_pool, -10, 10,
                                                                                             900000000000000000), self.our_address,
                                                                                    Fraction(10, 100))
        dai_usdc_mint_receipt = self.position_manager.mint(dai_usdc_mint_params).transact()
        assert dai_usdc_mint_receipt is not None and dai_usdc_mint_receipt.successful


        token_id = dai_usdc_mint_receipt.result[0].token_id
        print("minted_pool token_id", token_id)
        minted_position = self.position_manager.positions(token_id, dai_usdc_pool.token_0, dai_usdc_pool.token_1)
        print("minted dai_usdc value", self.position_manager.price_position(token_id, 1))
        return minted_position.pool

    def test_encode_route_to_path_multihop_input(self):
        """ Create 3 tokens, and two pools with one shared token between them. Encode the exact input path across these pools."""
        test_token_1 = Token("test_1", Address("0x0000000000000000000000000000000000000001"), 18)
        test_token_2 = Token("test_2", Address("0x0000000000000000000000000000000000000002"), 18)
        test_token_3 = Token("test_3", Address("0x0000000000000000000000000000000000000003"), 18)

        test_pool_1_medium = Pool(test_token_1, test_token_2, 3000, self.get_starting_sqrt_ratio(1, 1), 0, 0, [])
        test_pool_2_low = Pool(test_token_2, test_token_3, 500, self.get_starting_sqrt_ratio(1, 1), 0, 0, [])
        path = [test_pool_1_medium, test_pool_2_low]
        route = Route(path, test_token_1, test_token_3)

        encoded_path = self.swap_router.encode_route_to_path(route, False)
        assert encoded_path == '0x0000000000000000000000000000000000000001000bb800000000000000000000000000000000000000020001f40000000000000000000000000000000000000003'

    def test_encode_route_to_path_multihop_output(self):
        """ Create 3 tokens, and two pools with one shared token between them. Encode the exact output path across these pools."""
        test_token_1 = Token("test_1", Address("0x0000000000000000000000000000000000000001"), 18)
        test_token_2 = Token("test_2", Address("0x0000000000000000000000000000000000000002"), 18)
        test_token_3 = Token("test_3", Address("0x0000000000000000000000000000000000000003"), 18)

        test_pool_1_medium = Pool(test_token_1, test_token_2, 3000, self.get_starting_sqrt_ratio(1, 1), 0, 0, [])
        test_pool_2_low = Pool(test_token_2, test_token_3, 500, self.get_starting_sqrt_ratio(1, 1), 0, 0, [])
        path = [test_pool_1_medium, test_pool_2_low]
        route = Route(path, test_token_1, test_token_3)

        encoded_path = self.swap_router.encode_route_to_path(route, True)
        assert encoded_path == '0x00000000000000000000000000000000000000030001f40000000000000000000000000000000000000002000bb80000000000000000000000000000000000000001'

    def test_should_find_swap_path_across_multiple_pools_exact_input(self, position_manager_helpers):
        # deploy both pools
        weth_dai_pool = self.deploy_and_mint_weth_dai(position_manager_helpers)
        dai_usdc_pool = self.deploy_and_mint_dai_usdc(position_manager_helpers)

        # set trade params
        weth_in = Wad.from_number(.000000000001)
        # weth_in = Wad.from_number(1)
        # weth_in = 1
        print(Wad.from_number(1).value)
        recipient = self.our_address
        slippage_tolerance = Fraction(20, 100)
        deadline = int(time.time() + 1000)

        # define route from weth to usdc via dai
        path = [weth_dai_pool, dai_usdc_pool]
        route = Route(path, self.token_weth, self.token_usdc)

        encoded_path = self.swap_router.encode_route_to_path(route, False)

        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(self.token_weth, weth_in.value), TRADE_TYPE.EXACT_INPUT.value)
        usdc_out = trade.minimum_amount_out(slippage_tolerance).quotient()
        print("usdc out trade", usdc_out)

        assert usdc_out > 0

        usdc_out_quoter = self.swap_router.quote_exact_input(encoded_path, weth_in)
        print("usdc_out quoter", usdc_out_quoter)

        exact_input_params = ExactInputParams(self.web3, self.SwapRouter_abi, encoded_path, recipient, deadline, weth_in.value, usdc_out)

        swap = self.swap_router.swap_exact_input(exact_input_params).transact()
        assert swap is not None and swap.successful

    def test_should_find_swap_path_across_multiple_pools_exact_output(self, position_manager_helpers):
        # check if pool is already deployed; else retrieve existing pool infromation from the address
        weth_dai_pool_address = self.position_manager.get_pool_address(self.token_weth, self.token_dai, FEES.MEDIUM.value)
        dai_usdc_pool_address = self.position_manager.get_pool_address(self.token_dai, self.token_usdc, FEES.LOW.value)

        if isinstance(weth_dai_pool_address, Address) and weth_dai_pool_address != Address("0x0000000000000000000000000000000000000000"):
            weth_dai_pool = self.position_manager.get_pool(weth_dai_pool_address, self.token_weth, self.token_dai, 1)
        else:
            weth_dai_pool = self.deploy_and_mint_weth_dai(position_manager_helpers)

        if isinstance(dai_usdc_pool_address, Address) and dai_usdc_pool_address != Address("0x0000000000000000000000000000000000000000"):
            dai_usdc_pool = self.position_manager.get_pool(dai_usdc_pool_address, self.token_dai, self.token_usdc, 1)
        else:
            dai_usdc_pool = self.deploy_and_mint_dai_usdc(position_manager_helpers)

        # set trade params
        weth_out = Wad.from_number(.000000000001)
        # weth_out = Wad.from_number(1)
        recipient = self.our_address
        slippage_tolerance = Fraction(20, 100)
        deadline = int(time.time() + 1000)

        # define route from weth to usdc via dai
        path = [weth_dai_pool, dai_usdc_pool]
        route = Route(path, self.token_weth, self.token_usdc)
        encoded_path = self.swap_router.encode_route_to_path(route, True)

        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(self.token_weth, weth_out.value), TRADE_TYPE.EXACT_INPUT.value)
        usdc_in = trade.minimum_amount_out(slippage_tolerance).quotient()
        print("usdc_in trade: ", usdc_in)

        assert usdc_in > 0

        # usdc_in_quoter = self.swap_router.quote_exact_output(encoded_path, weth_out)
        # print("usdc_in quoter", usdc_in_quoter)

        exact_output_params = ExactOutputParams(self.web3, self.SwapRouter_abi, encoded_path, recipient, deadline, weth_out.value,
                                              usdc_in)

        swap = self.swap_router.swap_exact_output(exact_output_params).transact()
        assert swap is not None and swap.successful

    def test_should_error_when_pools_on_different_networks(self):
        """ test that both pools have matching chain_id value """
        test_token_1 = Token("test_1", Address("0x0000000000000000000000000000000000000001"), 18)
        test_token_2 = Token("test_2", Address("0x0000000000000000000000000000000000000002"), 18)
        test_token_3 = Token("test_3", Address("0x0000000000000000000000000000000000000003"), 18)

        test_pool_1_medium = Pool(test_token_1, test_token_2, 3000, self.get_starting_sqrt_ratio(1, 1), 0, 0, [], 1)
        test_pool_2_low = Pool(test_token_2, test_token_3, 500, self.get_starting_sqrt_ratio(1, 1), 0, 0, [], 2)
        path = [test_pool_1_medium, test_pool_2_low]

        with pytest.raises(Exception):
            route = Route(path, test_token_1, test_token_3)
