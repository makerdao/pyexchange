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

import pytest
from web3 import EthereumTesterProvider, Web3

from pyexchange.idex import IDEX
from pymaker import Address
from pymaker.approval import directly
from pymaker.numeric import Wad
from pymaker.token import DSToken


class TestIDEX:
    def setup_method(self):
        self.web3 = Web3(EthereumTesterProvider())
        self.web3.eth.defaultAccount = self.web3.eth.accounts[0]
        self.our_address = Address(self.web3.eth.defaultAccount)
        self.idex = IDEX.deploy(self.web3, self.our_address)
        self.idex._contract.transact().setInactivityReleasePeriod(0)

        self.token = DSToken.deploy(self.web3, 'AAA')
        self.token.mint(Wad.from_number(100)).transact()

    def test_fail_when_no_contract_under_that_address(self):
        # expect
        with pytest.raises(Exception):
            IDEX(web3=self.web3, address=Address('0xdeadadd1e5500000000000000000000000000000'))

    def test_correct_deployment(self):
        # expect
        assert self.idex is not None
        assert self.idex.address is not None
        assert self.idex.fee_account() == self.our_address

    def test_approval(self):
        # given
        assert self.token.allowance_of(self.our_address, self.idex.address) == Wad(0)

        # when
        self.idex.approve([self.token], directly())

        # then
        assert self.token.allowance_of(self.our_address, self.idex.address) > Wad(0)

    def test_deposit_and_balance_of_and_withdraw_for_raw_eth(self):
        # when
        self.idex.deposit(Wad.from_number(13)).transact()

        # then
        assert self.idex.balance_of(self.our_address) == Wad.from_number(13)

        # when
        self.idex.withdraw(Wad.from_number(2.5)).transact()

        # then
        assert self.idex.balance_of(self.our_address) == Wad.from_number(10.5)

    def test_deposit_and_balance_of_and_withdraw_for_token(self):
        # given
        self.idex.approve([self.token], directly())

        # when
        self.idex.deposit_token(self.token.address, Wad.from_number(13)).transact()

        # then
        assert self.idex.balance_of_token(self.token.address, self.our_address) == Wad.from_number(13)

        # when
        self.idex.withdraw_token(self.token.address, Wad.from_number(2.5)).transact()

        # then
        assert self.idex.balance_of_token(self.token.address, self.our_address) == Wad.from_number(10.5)

    def test_should_have_printable_representation(self):
        assert repr(self.idex) == f"IDEX('{self.idex.address}')"
