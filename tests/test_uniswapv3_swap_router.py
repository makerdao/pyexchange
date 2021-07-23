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

from web3 import Web3, HTTPProvider

from pyexchange.uniswapv3 import SwapRouter, PositionManager
from pyexchange.uniswapv3_calldata_params import ExactOutputSingleParams
from pyexchange.uniswapv3_constants import TRADE_TYPE, FEES
from pyexchange.uniswapv3_entities import Pool, Position, Trade, CurrencyAmount, Route, Fraction
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token


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

    def setup_class(self, position_manager_helpers):
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555"))
        self.web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
        register_private_key(self.web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")

        self.our_address = Address(self.web3.eth.defaultAccount)

        # constructor args for SwapRouter
        self.factory_address: Address = self._deploy(self.web3, self.UniswapV3Factory_abi, self.UniswapV3Factory_bin, [])
        self.weth_address: Address = self._deploy(self.web3, self.weth_abi, self.weth_bin, [])
        self.token_descriptor_address: Address = self._deploy(self.web3, self.NFTDescriptor_abi, self.NFTDescriptor_bin, [])

        self.swap_router_address = self._deploy(self.web3, self.SwapRouter_abi, self.SwapRouter_bin, [self.factory_address.address, self.weth_address.address])
        self.nonfungiblePositionManager_address = self._deploy(self.web3, self.NonfungiblePositionManager_abi, self.NonfungiblePositionManager_bin, [self.factory_address.address, self.weth_address.address, self.token_descriptor_address.address])
        self.tick_lens_address = self._deploy(self.web3, self.UniswapV3TickLens_abi, self.UniswapV3TickLens_bin, [])

        self.position_manager = PositionManager(self.web3, self.nonfungiblePositionManager_address, self.factory_address, self.tick_lens_address, self.weth_address)
        self.swap_router = SwapRouter(self.web3, self.swap_router_address)

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
        dai_balance = Wad.from_number(10000)
        usdc_balance = Wad.from_number(10000)

        self.ds_dai.mint(dai_balance).transact(from_address=self.our_address)
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(usdc_balance)).transact(from_address=self.our_address)

        # deploy weth_dai pool and mint initial liquidity to swap against
        position_manager_helper_wethdai = position_manager_helpers(self.web3, self.position_manager,
                                                           self.NonfungiblePositionManager_abi, self.token_weth,
                                                           self.token_dai)
        weth_dai_pool = position_manager_helper_wethdai.create_and_initialize_pool(self.get_starting_sqrt_ratio(1900, 1), FEES.MEDIUM.value)

        # wrap weth for testing (univ3 only uses weth)
        position_manager_helper_wethdai.wrap_eth(Wad.from_number(1), self.our_address)

        weth_dai_mint_params = position_manager_helper_wethdai.generate_mint_params(weth_dai_pool, Position(weth_dai_pool, -60, 60, 10), self.our_address, Fraction(20, 100))
        weth_dai_mint_receipt = self.position_manager.mint(weth_dai_mint_params).transact()
        assert weth_dai_mint_receipt is not None and weth_dai_mint_receipt.successful

        # deploy dai_usdc pool and mint initial liquidity to swap against
        position_manager_helper_daiusdc = position_manager_helpers(self.web3, self.position_manager,
                                                                   self.NonfungiblePositionManager_abi, self.token_dai,
                                                                   self.token_usdc)
        dai_usdc_pool = position_manager_helper_daiusdc.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1),
                                                                           FEES.LOW.value)
        dai_usdc_mint_params = position_manager_helper_daiusdc.generate_mint_params(dai_usdc_pool, Position(dai_usdc_pool, -10, 10, 10), self.our_address, Fraction(10, 100))
        dai_usdc_mint_receipt = self.position_manager.mint(dai_usdc_mint_params).transact()
        assert dai_usdc_mint_receipt is not None and dai_usdc_mint_receipt.successful

    def setup_method(self):
        pass

    def test_should_swap_usdc_for_dai_exact_output_single(self):
        amount_out = 100
        pool = Pool()
        route = Route(pool, self.token_usdc, self.token_dai)
        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(self.token_dai, amount_out), TRADE_TYPE.EXACT_OUTPUT_SINGLE.value)
        recipient = self.our_address
        slippage_tolerance = Fraction(20, 100) # equivalent to 0.2
        amount_in = trade.maximum_amount_in(slippage_tolerance)
        deadline = int(time.time() + 10000)
        price_limit = None
        exact_output_single_params = ExactOutputSingleParams(self.web3, trade.route.token_path[0], trade.route.token_path[1], trade.route.pools[0].fee, recipient, deadline, amount_out, amount_in, price_limit)

        swap = self.swap_router.swap_exact_output_single(exact_output_single_params).transact()

        assert swap is not None and swap.successful

    def test_should_find_swap_path_across_multiple_pools(self, position_manager_helpers):
        pass

    def test_should_revert_if_insufficient_output_liquidity(self):
        pass

    def test_should_revert_if_deadline_passed(self):
        deadline = int(time.time())

    def test_should_swap_when_eth_is_input(self, position_manager_helpers):
        position_manager_helper = position_manager_helpers(self.web3, self.position_manager, self.NonfungiblePositionManager_abi, self.token_weth, self.token_dai)

        pool = position_manager_helper.create_and_initialize_pool(self.get_starting_sqrt_ratio(1900, 1), FEES.MEDIUM.value)

        position_manager_helper.wrap_eth(Wad.from_number(1), self.our_address)

        mint_params = position_manager_helper.generate_mint_params(pool, Position(pool, -60, 60, 10), self.our_address,
                                                                   Fraction(20, 100))

        mint_receipt = self.position_manager.mint(mint_params).transact()
        assert mint_receipt is not None and mint_receipt.successful

    def test_should_swap_when_eth_is_output(self):
        pass

    def test_trade_amount_out_match_quoter(self):
        """ check on chain calls to quoter methods matches local Trade entity calculations """
