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
from web3 import EthereumTesterProvider, Web3, HTTPProvider

from eth_tester import EthereumTester, PyEVMBackend
import eth_tester.backends.pyevm.main as py_evm_main

from pyexchange.uniswapv2 import UniswapV2
from pyexchange.uniswap_staking_rewards import UniswapStakingRewards
from pyexchange.model import Pair
from pymaker import Address, Contract, Receipt, Transact
from pymaker.approval import directly
from pymaker.deployment import deploy_contract
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token
from pymaker.model import Token
from pymaker.keys import register_private_key


class TestUniswapStakingRewards(Contract):
    """
    In order to run automated tests locally, all dependent contracts and deployable bytecode need to be available for deploying contract to local network. 
    Deployable bytecode differs from the runtime bytecode you would see on Etherscan.

    """
    staking_rewards_factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniStakingRewardsFactory.abi')['abi']
    staking_rewards_factory_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniStakingRewardsFactory.bin')
    staking_rewards_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniStakingRewards.abi')['abi']
    staking_rewards_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniStakingRewards.bin')
    
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

        self.ds_reward_token = DSToken.deploy(self.web3, 'REWARD')
        self.reward_token = Token("REWARD", self.ds_reward_token.address, 18)

        # Deploy UniswapV2 contracts and set liquidity token
        self.liquidity_token = self.deploy_liquidity_token()

        self.staking_rewards_address = self._deploy(self.web3, self.staking_rewards_abi, self.staking_rewards_bin, [self.our_address.address, self.reward_token.address.address, self.liquidity_token.address.address])

        self.uniswap_staking_rewards = UniswapStakingRewards(self.web3, self.our_address, Address(self.staking_rewards_address), "UniswapStakingRewards")

        ## Useful for debugging failing transactions
        logger = logging.getLogger('eth')
        logger.setLevel(8)
        # Transact.gas_estimate_for_bad_txs = 210000

    def deploy_staking_rewards_factory():
        genesis_block_timestamp = int(self.web3.eth.getBlock('latest')['timestamp'])
        self.staking_rewards_factory_address = self._deploy(self.web3, self.staking_rewards_factory_abi, self.staking_rewards_factory_bin, [self.reward_token.address.address, genesis_block_timestamp + 10])
        self.staking_rewards_factory_contract = self._get_contract(self.web3, self.staking_rewards_factory_abi, self.staking_rewards_factory_address)

        self.liquidity_token = self.deploy_liquidity_token()

        staking_rewards_deploy_args = [self.liquidity_token.address.address, 10000]
        staking_rewards_deploy_tx = Transact(self, self.web3, self.staking_rewards_factory_abi, self.staking_rewards_factory_address, self.staking_rewards_factory_contract,
                        'deploy', staking_rewards_deploy_args)

        receipt = staking_rewards_deploy_tx.transact(from_address=self.our_address)
        # TODO: retrieve deployed StakingRewards contract address

    def deploy_liquidity_token(self) -> Token:

        # deploy uniswap contracts
        self.weth_address = self._deploy(self.web3, self.weth_abi, self.weth_bin, [])
        self.factory_address = self._deploy(self.web3, self.factory_abi, self.factory_bin, [self.our_address.address])
        self.router_address = self._deploy(self.web3, self.router_abi, self.router_bin, [self.factory_address.address, self.weth_address.address])
        self._weth_contract = self._get_contract(self.web3, self.weth_abi, self.weth_address)

        # deploy dai contract and instantiate DAI token
        self.ds_dai = DSToken.deploy(self.web3, 'DAI')
        self.token_dai = Token("DAI", self.ds_dai.address, 18)
        self.token_weth = Token("WETH", self.weth_address, 18)

        # self.dai_usdc_uniswap = UniswapV2(self.web3, self.token_dai, self.token_usdc, self.our_address, self.router_address, self.factory_address)
        self.dai_eth_uniswap = UniswapV2(self.web3, self.token_dai, self.token_weth, self.our_address, self.router_address, self.factory_address)

        # add liquidity
        self.add_liquidity_eth()

        # set liquidity token
        self.dai_eth_uniswap.set_pair_token(self.dai_eth_uniswap.get_pair_address(self.token_dai.address, self.token_weth.address))
        liquidity_token = self.dai_eth_uniswap.pair_token

        return liquidity_token

    def add_liquidity_eth(self) -> Receipt:
        self.ds_dai.mint(Wad(300 * 10**18)).transact(from_address=self.our_address)
        self.dai_eth_uniswap.approve(self.token_dai)
        self.dai_eth_uniswap.approve(self.token_weth)

        add_liquidity_eth_args = {
            "amount_b_desired": Wad.from_number(28),
            "amount_a_desired": Wad.from_number(.1),
            "amount_b_min":  Wad.from_number(25),
            "amount_a_min": Wad.from_number(0.01)
        }

        return self.dai_eth_uniswap.add_liquidity_eth(add_liquidity_eth_args, self.token_dai, 0).transact(from_address=self.our_address)

    def test_staking(self):
        # given
        self.uniswap_staking_rewards.approve(self.liquidity_token.address)
        stake_receipt = self.uniswap_staking_rewards.stake_liquidity(Wad(10)).transact(from_address=self.our_address)

        # when
        balance = self.uniswap_staking_rewards.balance_of()

        # then
        assert balance > Wad.from_number(0)
        # TODO: add tests to check that expected balance is correct

    def test_withdraw(self):
        # given
        self.uniswap_staking_rewards.approve(self.liquidity_token.address)
        stake_receipt = self.uniswap_staking_rewards.stake_liquidity(Wad(10)).transact(from_address=self.our_address)

        # when
        balance = self.uniswap_staking_rewards.balance_of()

        # then
        assert balance > Wad.from_number(0)

        # when
        withdraw_receipt = self.uniswap_staking_rewards.withdraw_liquidity(Wad(10)).transact(from_address=self.our_address)
        balance = self.uniswap_staking_rewards.balance_of()

        # then
        assert balance == Wad.from_number(0)

    def test_exit(self):
        # given
        self.uniswap_staking_rewards.approve(self.liquidity_token.address)
        stake_receipt = self.uniswap_staking_rewards.stake_liquidity(Wad(10)).transact(from_address=self.our_address)

        # when
        balance = self.uniswap_staking_rewards.balance_of()

        # then
        assert balance > Wad.from_number(0)

        # when
        stake_receipt = self.uniswap_staking_rewards.withdraw_all_liquidity().transact(from_address=self.our_address)
        balance = self.uniswap_staking_rewards.balance_of()

        # then
        assert balance == Wad.from_number(0)

    # def test_reward_accumulation(self):
    #     # given
    #     self.uniswap_staking_rewards.approve(self.liquidity_token.address)
    #     stake_receipt = self.uniswap_staking_rewards.stake_liquidity(Wad(10)).transact(from_address=self.our_address)

    #     time.sleep(15)

    #     earned = self.uniswap_staking_rewards.earned()

    #     reward_for_duration = self.uniswap_staking_rewards.get_rewards_for_duration()
    #     print("rewards for duration: ", reward_for_duration)

    #     assert earned > Wad(0)
