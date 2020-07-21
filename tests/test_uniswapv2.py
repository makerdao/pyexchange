# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway
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
from web3 import EthereumTesterProvider, Web3

from eth_tester import EthereumTester, PyEVMBackend
import eth_tester.backends.pyevm.main as py_evm_main

from pyexchange.uniswapv2 import UniswapV2
from pyexchange.model import Pair
from pymaker import Address, Contract, Transact
from pymaker.approval import directly
from pymaker.deployment import deploy_contract
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token
from pymaker.model import Token
import unittest

class TestUniswapV2(Contract):

    pair_abi = Contract._load_abi(__name__, '../pyexchange/abi/IUniswapV2Pair.abi')
    router_abi = Contract._load_abi(__name__, '../pyexchange/abi/IUniswapV2Router02.abi')
    router_bin = Contract._load_bin(__name__, '../pyexchange/abi/IUniswapV2Router02.bin')
    factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/IUniswapV2Factory.abi')
    factory_bin = Contract._load_bin(__name__, '../pyexchange/abi/IUniswapV2Factory.bin')

    def setup_method(self):
        py_evm_main.GENESIS_GAS_LIMIT = 10000000
        self.web3 = Web3(EthereumTesterProvider(EthereumTester(PyEVMBackend())))
        self.web3.eth.defaultAccount = self.web3.eth.accounts[0]
        self.our_address = Address(self.web3.eth.defaultAccount)

        self.router_address = self._deploy(self.web3, self.router_abi['abi'], self.router_bin, [])
        self.factory_address = self._deploy(self.web3, self.factory_abi['abi'], self.factory_bin, [])
        self._router_contract = self._get_contract(self.web3, self.router_abi['abi'], self.router_address)
        self._factory_contract = self._get_contract(self.web3, self.factory_abi['abi'], self.factory_address)

        self.ds_dai = DSToken.deploy(self.web3, 'DAI')
        self.ds_usdc = DSToken.deploy(self.web3, 'USDC')

        self.token_dai = Token("DAI", self.ds_dai.address, 18)
        self.token_usdc = Token("USDC", self.ds_usdc.address, 6)
        self.dai_usdc_uniswap = UniswapV2(self.web3, self.token_dai, self.token_usdc, self.router_address, self.factory_address)
        
        # print(self.web3.eth.getCode(self.router_address.address))

        # Useful for debugging failing transactions
        logger = logging.getLogger('eth')
        # logger.setLevel(8)
        # Transact.gas_estimate_for_bad_txs = 210000

    def test_approval(self):
        # given
        assert self.ds_dai.allowance_of(self.our_address, self.router_address) == Wad(0)

        # when
        self.dai_usdc_uniswap.approve(self.token_dai)

        # then
        assert self.ds_dai.allowance_of(self.our_address, self.router_address) > Wad(0)

    def test_getting_token_balances(self):
        # given
        self.ds_dai.mint(Wad(17 * 10**18)).transact()
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(Wad.from_number(9))).transact()

        # when
        balance_dai = self.dai_usdc_uniswap.get_account_token_balance(self.token_dai)
        balance_usdc = self.dai_usdc_uniswap.get_account_token_balance(self.token_usdc)

        # then
        assert balance_dai == Wad.from_number(17)
        assert balance_usdc == Wad.from_number(9)

    def test_add_liquidity_tokens(self):
        # given
        self.ds_dai.mint(Wad(1700000000 * 10**18)).transact()
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(Wad.from_number(90000000000))).transact()
        self.dai_usdc_uniswap.approve(self.token_dai)
        self.dai_usdc_uniswap.approve(self.token_usdc)

        # # given
        # add_liquidity_tokens_args = {
        #     "amount_a_desired": Wad.from_number(1.9),
        #     "amount_b_desired": self.token_usdc.unnormalize_amount(Wad.from_number(2.0)),
        #     "amount_a_min": Wad.from_number(1.8),
        #     "amount_b_min": self.token_usdc.unnormalize_amount(Wad.from_number(1.9))
        # }

        # given
        add_liquidity_tokens_args = {
            "amount_a_desired": Wad.from_number(1.9),
            "amount_b_desired": Wad.from_number(2.0),
            "amount_a_min": Wad.from_number(1.8),
            "amount_b_min": Wad.from_number(1.9)
        }

        time.sleep(10)
        # when
        add_liquidity = self.dai_usdc_uniswap.add_liquidity(add_liquidity_tokens_args, self.token_dai, self.token_usdc).transact()

        # then
        assert add_liquidity.result == True

        # then
        assert self.dai_usdc_uniswap.get_current_liquidity() > Wad.from_number(0)

    def test_add_liquidity_eth(self):
        pass

    def test_get_exchange_rate(self):
        pass

    def test_remove_liquidity(self):
        pass

    def test_remove_liquidity_eth(self):
        pass
