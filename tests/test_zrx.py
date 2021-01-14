# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus
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

import pkg_resources
from web3 import EthereumTesterProvider, Web3, HTTPProvider

from eth_tester import EthereumTester, PyEVMBackend
import eth_tester.backends.pyevm.main as py_evm_main

from pyexchange.zrx import Pair, ZrxApi
from pyflex import Address
from pyflex.deployment import deploy_contract
from pyflex.numeric import Wad
from pyflex.token import DSToken, ERC20Token
from pyflex.zrx import ZrxExchange


class TestZrxApi:
    def setup_method(self):
        py_evm_main.GENESIS_GAS_LIMIT = 10000000
        #self.web3 = Web3(EthereumTesterProvider(EthereumTester(PyEVMBackend())))
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555"))
        self.web3.eth.defaultAccount = self.web3.eth.accounts[0]
        self.our_address = Address(self.web3.eth.defaultAccount)

        self.zrx_token = ERC20Token(web3=self.web3, address=deploy_contract(self.web3, 'ZRXToken'))
        self.token_transfer_proxy_address = deploy_contract(self.web3, 'TokenTransferProxy')
        self.exchange = ZrxExchange.deploy(self.web3, self.zrx_token.address, self.token_transfer_proxy_address)
        self.web3.eth.contract(abi=json.loads(pkg_resources.resource_string('pyflex.deployment', f'abi/TokenTransferProxy.abi')))(address=self.token_transfer_proxy_address.address).functions.addAuthorizedAddress(self.exchange.address.address).transact()

        self.zrx_api = ZrxApi(self.exchange)

        self.dgx = DSToken.deploy(self.web3, 'DGX', 'DGX')
        self.dai = DSToken.deploy(self.web3, 'DAI', 'DAI')
        self.pair = Pair(self.dgx.address, 9, self.dai.address, 18)

    def test_getting_balances(self):
        # given
        self.dgx.mint(Wad(17 * 10**9)).transact()
        self.dai.mint(Wad.from_number(17)).transact()

        # when
        balances = self.zrx_api.get_balances(self.pair)
        # then
        assert balances[0] == Wad.from_number(17)
        assert balances[1] == Wad.from_number(17)

    def test_sell_order(self):
        # when
        zrx_order = self.zrx_api.place_order(self.pair, True, Wad.from_number(45.0), Wad.from_number(5.0), 999)
        # then
        assert zrx_order.buy_token == self.dai.address
        assert zrx_order.buy_amount == Wad.from_number(5.0 * 45.0)
        assert zrx_order.pay_token == self.dgx.address
        assert zrx_order.pay_amount == Wad(5 * 10**9)
        assert zrx_order.expiration == 999

        # when
        orders = self.zrx_api.get_orders(self.pair, [zrx_order])
        # then
        assert orders[0].order_id is not None
        assert orders[0].is_sell is True
        assert orders[0].price == Wad.from_number(45.0)
        assert orders[0].amount == Wad.from_number(5.0)
        assert orders[0].zrx_order == zrx_order

    def test_buy_order(self):
        # when
        zrx_order = self.zrx_api.place_order(self.pair, False, Wad.from_number(45.0), Wad.from_number(5.0), 999)
        # then
        assert zrx_order.buy_token == self.dgx.address
        assert zrx_order.buy_amount == Wad(5 * 10**9)
        assert zrx_order.pay_token == self.dai.address
        assert zrx_order.pay_amount == Wad.from_number(5.0 * 45.0)
        assert zrx_order.expiration == 999

        # when
        orders = self.zrx_api.get_orders(self.pair, [zrx_order])
        # then
        assert orders[0].order_id is not None
        assert orders[0].is_sell is False
        assert orders[0].price == Wad.from_number(45.0)
        assert orders[0].amount == Wad.from_number(5.0)
        assert orders[0].zrx_order == zrx_order
