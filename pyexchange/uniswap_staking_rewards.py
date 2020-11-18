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
from web3 import Web3, HTTPProvider
from web3.eth import Contract as Web3Contract

from pymaker.lifecycle import Lifecycle
from pymaker.keys import register_keys
from pymaker.model import Token, TokenConfig
from pymaker import Contract, Address, Wad, Receipt, Transact
from pymaker.model import Token

from pyexchange.staking_rewards import StakingRewards


class UniswapStakingRewards(StakingRewards):
    """
        Uniswap implementation available here: https://github.com/Uniswap/liquidity-staker/blob/master/contracts/StakingRewards.sol
    """
    logger = logging.getLogger()

    staking_rewards_factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniStakingRewardsFactory.abi')['abi']
    staking_rewards_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniStakingRewards.abi')['abi']

    def __init__(self, web3: Web3, keeper_address: Address, contract_address: Address, contract_name: str):
        assert (isinstance(web3, Web3))
        assert (isinstance(keeper_address, Address))
        assert (isinstance(contract_address, Address))
        assert (isinstance(contract_name, str))

        self.contract = self._get_contract(web3, self.staking_rewards_abi, contract_address)

        super().__init__(web3, keeper_address, self.contract, self.staking_rewards_abi, contract_address, contract_name)

    def stake_liquidity(self, amount: Wad) -> Transact:
        assert (isinstance(amount, Wad))

        stake_liquidity_args = [
            amount.value
        ]

        return Transact(self, self.web3, self.contract_abi, self.contract_address, self.contract,
                'stake', stake_liquidity_args)

    def stake_liquidity_with_permit(self, amount: Wad, deadline: Wad, v, r, s) -> Transact:
        pass

    def withdraw_liquidity(self, amount: Wad) -> Transact:
        assert (isinstance(amount, Wad))

        withdraw_liquidity_args = [
            amount.value
        ]

        return Transact(self, self.web3, self.contract_abi, self.contract_address, self.contract,
                'withdraw', withdraw_liquidity_args)

    def withdraw_all_liquidity(self) -> Transact:
        return Transact(self, self.web3, self.contract_abi, self.contract_address, self.contract,
                        'exit', [])
