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

import argparse
import logging
import sys

from typing import List
from web3 import Web3
from web3.eth import Contract as Web3Contract

from pymaker import Contract, Address, Wad, Receipt, Transact
from pymaker.approval import directly
from pymaker.token import DSToken, ERC20Token
from pymaker.model import Token


class StakingRewards(Contract):
    """    
        Yield farming commonly uses Synthetix's IStakingRewards contract:
        https://docs.synthetix.io/contracts/source/interfaces/istakingrewards/
    """

    def __init__(self, web3: Web3, keeper_address: Address, contract: Web3Contract, contract_abi: List, contract_address: Address, contract_name: str):
        assert (isinstance(web3, Web3))
        assert (isinstance(keeper_address, Address))
        assert (isinstance(contract, Web3Contract))
        assert (isinstance(contract_abi, List))
        assert (isinstance(contract_address, Address))
        assert (isinstance(contract_name, str))

        self.web3 = web3

        self.keeper_address = keeper_address
        self.contract = contract
        self.contract_abi = contract_abi
        self.contract_address = contract_address
        self.contract_name = contract_name

    def approve(self, token_address: Address):
        assert (isinstance(token_address, Address))

        erc20_token = ERC20Token(self.web3, token_address)

        approval_function = directly()
        return approval_function(erc20_token, self.contract_address, self.contract_name)

    def balance_of(self) -> Wad:
        return Wad(self.contract.functions.balanceOf(self.keeper_address.address).call())

    # earned naming may not be standardized
    def earned(self) -> Wad:
        return Wad(self.contract.functions.earned(self.keeper_address.address).call())

    def get_balance(self) -> Wad:
        return self.balance_of() + self.earned(token)

    def get_rewards_for_duration(self) -> Wad:
        return Wad(self.contract.functions.getRewardForDuration().call())

    def stake_liquidity(self, amount: Wad) -> Transact:
        raise NotImplementedError()

    def stake_liquidity_with_permit(self, amount: Wad, deadline: Wad, v, r, s) -> Transact:
        raise NotImplementedError()

    def withdraw_liquidity(self, amount: Wad) -> Transact:
        raise NotImplementedError()

    def withdraw_all_liquidity(self) -> Transact:
        raise NotImplementedError()
