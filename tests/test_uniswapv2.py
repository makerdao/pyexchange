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
import pytest
import unittest

import pkg_resources
from web3 import Web3, HTTPProvider

import eth_tester.backends.pyevm.main as py_evm_main

from pyexchange.uniswapv2 import UniswapV2
from pyexchange.model import Pair
from pyflex import Address, Contract, Receipt, Transact
from pyflex.approval import directly
from pyflex.deployment import deploy_contract
from pyflex.numeric import Wad
from pyflex.token import DSToken, ERC20Token
from pyflex.model import Token
from pyflex.keys import register_keys, register_private_key

class TestUniswapV2(Contract):
    """
    In order to run automated tests locally, all dependent contracts and deployable bytecode need to be available for deploying contract to local network. 
    Deployable bytecode differs from the runtime bytecode you would see on Etherscan.

    """
    pair_abi = Contract._load_abi(__name__, '../pyexchange/abi/IUniswapV2Pair.abi')
    Irouter_abi = Contract._load_abi(__name__, '../pyexchange/abi/IUniswapV2Router02.abi')['abi']
    router_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV2Router02.abi')
    router_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV2Router02.bin')
    factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV2Factory.abi')
    factory_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV2Factory.bin')
    weth_abi = Contract._load_abi(__name__, '../pyexchange/abi/WETH.abi')
    weth_bin = Contract._load_bin(__name__, '../pyexchange/abi/WETH.bin')

    def setup_method(self):

        # Use Ganache docker container
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555"))
        self.web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
        register_private_key(self.web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")

        self.our_address = Address(self.web3.eth.defaultAccount)

        self.weth_address = self._deploy(self.web3, self.weth_abi, self.weth_bin, [])
        self.factory_address = self._deploy(self.web3, self.factory_abi, self.factory_bin, [self.our_address.address])
        self.router_address = self._deploy(self.web3, self.router_abi, self.router_bin, [self.factory_address.address, self.weth_address.address])
        self._weth_contract = self._get_contract(self.web3, self.weth_abi, self.weth_address)

        self.ds_systemcoin = DSToken.deploy(self.web3, 'SystemCoin', 'sys')
        self.ds_usdc = DSToken.deploy(self.web3, 'USDC', 'USDC')
        self.token_systemcoin = Token("SystemCoin", self.ds_systemcoin.address, 18)
        self.token_usdc = Token("USDC", self.ds_usdc.address, 6)
        self.token_weth = Token("WETH", self.weth_address, 18)

        self.systemcoin_usdc_uniswap = UniswapV2(self.web3, self.token_systemcoin, self.token_usdc, self.our_address, self.router_address, self.factory_address)
        self.systemcoin_eth_uniswap = UniswapV2(self.web3, self.token_systemcoin, self.token_weth, self.our_address, self.router_address, self.factory_address)
        
        ## Useful for debugging failing transactions
        logger = logging.getLogger('eth')
        logger.setLevel(8)
        # Transact.gas_estimate_for_bad_txs = 210000

    def add_liquidity_tokens(self) -> Receipt:
        self.ds_systemcoin.mint(Wad(17 * 10**18)).transact(from_address=self.our_address)
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(Wad.from_number(9))).transact(from_address=self.our_address)
        self.systemcoin_usdc_uniswap.approve(self.token_systemcoin)
        self.systemcoin_usdc_uniswap.approve(self.token_usdc)

        add_liquidity_tokens_args = {
            "amount_a_desired": Wad.from_number(1.9),
            "amount_b_desired": self.token_usdc.unnormalize_amount(Wad.from_number(2.0)),
            "amount_a_min": Wad.from_number(1.8),
            "amount_b_min": self.token_usdc.unnormalize_amount(Wad.from_number(1.9))
        }

        return self.systemcoin_usdc_uniswap.add_liquidity(add_liquidity_tokens_args, self.token_systemcoin, self.token_usdc).transact(from_address=self.our_address)

    def add_liquidity_eth(self) -> Receipt:
        self.ds_systemcoin.mint(Wad(300 * 10**18)).transact(from_address=self.our_address)
        self.systemcoin_eth_uniswap.approve(self.token_systemcoin)
        self.systemcoin_eth_uniswap.approve(self.token_weth)

        add_liquidity_eth_args = {
            "amount_b_desired": Wad.from_number(28),
            "amount_a_desired": Wad.from_number(.1),
            "amount_b_min":  Wad.from_number(25),
            "amount_a_min": Wad.from_number(0.01)
        }

        return self.systemcoin_eth_uniswap.add_liquidity_eth(add_liquidity_eth_args, self.token_systemcoin, 0).transact(from_address=self.our_address)

    def test_approval(self):
        # given
        assert self.ds_systemcoin.allowance_of(self.our_address, self.router_address) == Wad(0)

        # when
        self.systemcoin_usdc_uniswap.approve(self.token_systemcoin)

        # then
        assert self.ds_systemcoin.allowance_of(self.our_address, self.router_address) > Wad(0)

    def test_getting_token_balances(self):
        # given
        self.ds_systemcoin.mint(Wad(17 * 10**18)).transact()
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(Wad.from_number(9))).transact()

        # when
        balance_systemcoin = self.systemcoin_usdc_uniswap.get_account_token_balance(self.token_systemcoin)
        balance_usdc = self.systemcoin_usdc_uniswap.get_account_token_balance(self.token_usdc)

        # then
        assert balance_systemcoin == Wad.from_number(17)
        assert balance_usdc == Wad.from_number(9)

    def test_add_liquidity_tokens(self):
        # when
        add_liquidity = self.add_liquidity_tokens()

        # then
        assert add_liquidity.successful == True

        # when
        self.systemcoin_usdc_uniswap.set_and_approve_pair_token(self.systemcoin_usdc_uniswap.get_pair_address(self.token_systemcoin.address, self.token_usdc.address))

        # then
        assert self.systemcoin_usdc_uniswap.get_current_liquidity() > Wad.from_number(0)

    def test_add_liquidity_eth(self):
        # when
        add_liquidity_eth = self.add_liquidity_eth()

        # then
        assert add_liquidity_eth.successful == True

        # when
        self.systemcoin_eth_uniswap.set_and_approve_pair_token(self.systemcoin_usdc_uniswap.get_pair_address(self.token_systemcoin.address, self.token_weth.address))

        # then
        assert self.systemcoin_eth_uniswap.get_current_liquidity() > Wad.from_number(0)

    def test_remove_liquidity_tokens(self):
        # given
        add_liquidity = self.add_liquidity_tokens()
        self.systemcoin_usdc_uniswap.set_and_approve_pair_token(self.systemcoin_usdc_uniswap.get_pair_address(self.token_systemcoin.address, self.token_usdc.address))

        current_liquidity = self.systemcoin_usdc_uniswap.get_current_liquidity()
        total_liquidity = self.systemcoin_usdc_uniswap.get_total_liquidity()
        systemcoin_exchange_balance = self.systemcoin_usdc_uniswap.get_exchange_balance(self.token_systemcoin, self.systemcoin_usdc_uniswap.pair_address)
        usdc_exchange_balance = self.token_usdc.unnormalize_amount(self.systemcoin_usdc_uniswap.get_exchange_balance(self.token_usdc, self.systemcoin_usdc_uniswap.pair_address))

        # then
        assert current_liquidity > Wad.from_number(0)
        assert total_liquidity > Wad.from_number(0)
        assert total_liquidity > current_liquidity

        # given
        amount_a_min = current_liquidity * systemcoin_exchange_balance / total_liquidity
        amount_b_min = current_liquidity * usdc_exchange_balance / total_liquidity
        remove_liquidity_tokens_args = {
            "liquidity": current_liquidity,
            "amountAMin": amount_a_min,
            "amountBMin": amount_b_min
        }

        # when
        remove_liquidity = self.systemcoin_usdc_uniswap.remove_liquidity(remove_liquidity_tokens_args, self.token_systemcoin, self.token_usdc).transact(from_address=self.our_address)

        # then
        assert remove_liquidity.successful == True
        assert self.systemcoin_usdc_uniswap.get_current_liquidity() == Wad.from_number(0)

    def test_remove_liquidity_eth(self):
        # given
        add_liquidity_eth = self.add_liquidity_eth()
        self.systemcoin_eth_uniswap.set_and_approve_pair_token(self.systemcoin_eth_uniswap.get_pair_address(self.token_systemcoin.address, self.token_weth.address))

        current_liquidity = self.systemcoin_eth_uniswap.get_current_liquidity()
        total_liquidity = self.systemcoin_eth_uniswap.get_total_liquidity()
        systemcoin_exchange_balance = self.systemcoin_eth_uniswap.get_exchange_balance(self.token_systemcoin, self.systemcoin_eth_uniswap.pair_address)
        weth_exchange_balance = self.systemcoin_eth_uniswap.get_exchange_balance(self.token_weth, self.systemcoin_eth_uniswap.pair_address)

        # then
        assert current_liquidity > Wad.from_number(0)
        assert total_liquidity > Wad.from_number(0)
        assert total_liquidity > current_liquidity
        
        # given
        amount_a_min = current_liquidity * weth_exchange_balance / total_liquidity
        amount_b_min = current_liquidity * systemcoin_exchange_balance / total_liquidity
        remove_liquidity_eth_args = {
            "liquidity": current_liquidity,
            "amountBMin": amount_b_min,
            "amountAMin": amount_a_min
        }

        # when
        remove_liquidity = self.systemcoin_eth_uniswap.remove_liquidity_eth(remove_liquidity_eth_args, self.token_systemcoin, 0).transact(from_address=self.our_address)

        # then
        assert remove_liquidity.successful == True
        assert self.systemcoin_eth_uniswap.get_current_liquidity() == Wad.from_number(0)

    def test_tokens_swap(self):
        # given
        add_liquidity = self.add_liquidity_tokens()

        balance_systemcoin_before_swap = self.systemcoin_usdc_uniswap.get_account_token_balance(self.token_systemcoin)
        balance_usdc_before_swap = self.systemcoin_usdc_uniswap.get_account_token_balance(self.token_usdc)

        # when
        swap = self.systemcoin_usdc_uniswap.swap_exact_tokens_for_tokens(Wad.from_number(.2), self.token_usdc.unnormalize_amount(Wad.from_number(.01)), [self.ds_systemcoin.address.address, self.ds_usdc.address.address]).transact(from_address=self.our_address)
        
        # then
        assert swap.successful == True

        balance_systemcoin_after_swap = self.systemcoin_usdc_uniswap.get_account_token_balance(self.token_systemcoin)
        balance_usdc_after_swap = self.systemcoin_usdc_uniswap.get_account_token_balance(self.token_usdc)

        assert balance_systemcoin_after_swap < balance_systemcoin_before_swap
        assert balance_usdc_before_swap < balance_usdc_after_swap
