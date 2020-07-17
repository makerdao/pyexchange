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

import pkg_resources
from web3 import EthereumTesterProvider, Web3

from eth_tester import EthereumTester, PyEVMBackend
import eth_tester.backends.pyevm.main as py_evm_main

from pyexchange.uniswapv2 import UniswapV2
from pyexchange.model import Pair
from pymaker import Address, Contract
from pymaker.approval import directly
from pymaker.deployment import deploy_contract
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token
from pymaker.model import Token
import unittest

@unittest.skip("TestUniswapV2 testing skipping")
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

        print(self.router_address, self.factory_address, __name__)

        # self.dai_token = ERC20Token(web3=self.web3, address=deploy_contract(self.web3,abi 'DAIToken'))
        # self.token_transfer_proxy_address = deploy_contract(self.web3, 'TokenTransferProxy')
        # self.exchange = ZrxExchange.deploy(self.web3, self.zrx_token.address, self.token_transfer_proxy_address)
        # TODO: deploy the other uniswap v2 contracts
        # self.web3.eth.contract(abi=json.loads(pkg_resources.resource_string('pymaker.deployment', f'abi/TokenTransferProxy.abi')))(address=self.token_transfer_proxy_address.address).functions.addAuthorizedAddress(self.exchange.address.address).transact()

        # self.dgx = DSToken.deploy(self.web3, 'DGX')
        self.dai = DSToken.deploy(self.web3, 'DAI')

        # Kovan token addresses
        self.token_a = Token("DAI", Address("0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa"), 18)
        self.token_b = Token("USDC", Address("0x198419c5c340e8de47ce4c0e4711a03664d42cb2"), 6)
        self.uniswap = UniswapV2(self.web3, self.token_a, self.token_b)

    def test_get_block(self):
        assert isinstance(self.uniswap.get_block(), int)

    def test_approval(self):
        # given
        assert self.dai.allowance_of(self.our_address, self.router_address) == Wad(0)

        # when
        # self._router_contract.approve([self.dai], directly())
        approval_function = directly()
        
        approval_function(self.dai, self.router_address, 'IUniswapV2Router02')

        # then
        assert self.dai.allowance_of(self.our_address, self.router_address) > Wad(0)

    def test_getting_balances(self):
        # given
        # self.dgx.mint(Wad(17 * 10**9)).transact()
        self.uniswap.get_account_token_balance(self.token_a)\
            # mint(Wad.from_number(17)).transact()

        # when
        # balances = self.uniswap.get_balances(self.pair)
        # then
        # assert balances[0] == Wad.from_number(17)
        # assert balances[1] == Wad.from_number(17)

    def test_add_liquidity_eth(self):

        eth_pair_amounts = {
            "amount_token_desired": self.web3.toWei(24, 'ether'),
            "amount_token_min": self.web3.toWei(21, 'ether'),
            "amount_eth_min": self.web3.toWei(.1, 'ether')
        }

        approval_function = directly()
        approval_function(self.dai, self.router_address, 'IUniswapV2Router02')

        time.sleep(20)
        # when
        add_liquidity = self.uniswap.add_liquidity_eth(eth_pair_amounts, self.dai.address).transact()

        # then
        assert add_liquidity.result == True

        # when
        # orders = self.uniswap.get_orders(self.pair, [add_liquidity])
        # # then
        # assert orders[0].order_id is not place_order
        # assert orders[0].is_sell is True
        # assert orders[0].price == Wad.from_number(45.0)
        # assert orders[0].amount == Wad.from_number(5.0)
        # assert orders[0].add_liquidity == add_liquidity

    def test_remove_liquidity_eth(self):
        # when
        zrx_order = self.uniswap.place_order(self.pair, False, Wad.from_number(45.0), Wad.from_number(5.0), 999)
        # then
        assert zrx_order.buy_token == self.dgx.address
        assert zrx_order.buy_amount == Wad(5 * 10**9)
        assert zrx_order.pay_token == self.dai.address
        assert zrx_order.pay_amount == Wad.from_number(5.0 * 45.0)
        assert zrx_order.expiration == 999

        # when
        orders = self.uniswap.get_orders(self.pair, [zrx_order])
        # then
        assert orders[0].order_id is not None
        assert orders[0].is_sell is False
        assert orders[0].price == Wad.from_number(45.0)
        assert orders[0].amount == Wad.from_number(5.0)
        assert orders[0].zrx_order == zrx_order

    def test_swap():
        pass