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

import logging
from typing import List

import requests
from web3 import Web3

from pymaker import Contract, Address, Transact, Wad
from pymaker.token import ERC20Token


class IDEX(Contract):
    """A client for the IDEX Exchange contract.

    You can find the source code of the IDEX Exchange contract here:
    <https://etherscan.io/address/0x2a0c0dbecc7e4d658f48e01e3fa353f44050c208#code>.

    Some API docs can be found here:
    <https://github.com/AuroraDAO/idex-api-docs>.

    Attributes:
        web3: An instance of `Web` from `web3.py`.
        address: Ethereum address of the IDEX Exchange contract.
    """

    abi = Contract._load_abi(__name__, 'abi/IDEX.abi')
    bin = Contract._load_bin(__name__, 'abi/IDEX.bin')

    _ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")

    @staticmethod
    def deploy(web3: Web3, fee_account: Address):
        """Deploy a new instance of the IDEX Exchange contract.

        Args:
            web3: An instance of `Web` from `web3.py`.
            fee_account: The address of the account which will collect fees.

        Returns:
            An `IDEX` class instance.
        """
        return IDEX(web3=web3, address=Contract._deploy(web3, IDEX.abi, IDEX.bin, [fee_account.address]))

    def __init__(self, web3: Web3, address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(address, Address))

        self.web3 = web3
        self.address = address
        self._contract = self._get_contract(web3, self.abi, address)

    def fee_account(self) -> Address:
        """Returns the address of the fee account i.e. the account that receives all fees collected.

        Returns:
            The address of the fee account.
        """
        return Address(self._contract.call().feeAccount())

    def approve(self, tokens: List[ERC20Token], approval_function):
        """Approve the IDEX Exchange contract to fully access balances of specified tokens.

        For available approval functions (i.e. approval modes) see `directly` and `via_tx_manager`
        in `pymaker.approval`.

        Args:
            tokens: List of :py:class:`pymaker.token.ERC20Token` class instances.
            approval_function: Approval function (i.e. approval mode).
        """
        assert(isinstance(tokens, list))
        assert(callable(approval_function))

        for token in tokens:
            approval_function(token, self.address, 'IDEX Exchange contract')

    def deposit(self, amount: Wad) -> Transact:
        """Deposits `amount` of raw ETH to IDEX.

        Args:
            amount: Amount of raw ETH to be deposited on IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'deposit', [], {'value': amount.value})

    def withdraw(self, amount: Wad) -> Transact:
        """Withdraws `amount` of raw ETH from IDEX.

        The withdrawn ETH will get transferred to the calling account.

        Args:
            amount: Amount of raw ETH to be withdrawn from IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'withdraw',
                        [self._ZERO_ADDRESS.address, amount.value])

    def balance_of(self, user: Address) -> Wad:
        """Returns the amount of raw ETH deposited by the specified user.

        Args:
            user: Address of the user to check the balance of.

        Returns:
            The raw ETH balance kept in the IDEX Exchange contract by the specified user.
        """
        assert(isinstance(user, Address))
        return Wad(self._contract.call().balanceOf(self._ZERO_ADDRESS.address, user.address))

    def deposit_token(self, token: Address, amount: Wad) -> Transact:
        """Deposits `amount` of ERC20 token `token` to IDEX.

        Tokens will be pulled from the calling account, so the IDEX contract needs
        to have appropriate allowance. Either call `approve()` or set the allowance manually
        before trying to deposit tokens.

        Args:
            token: Address of the ERC20 token to be deposited.
            amount: Amount of token `token` to be deposited to IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(token, Address))
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'depositToken',
                        [token.address, amount.value])

    def withdraw_token(self, token: Address, amount: Wad) -> Transact:
        """Withdraws `amount` of ERC20 token `token` from IDEX.

        Tokens will get transferred to the calling account.

        Args:
            token: Address of the ERC20 token to be withdrawn.
            amount: Amount of token `token` to be withdrawn from IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(token, Address))
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'withdraw',
                        [token.address, amount.value])

    def balance_of_token(self, token: Address, user: Address) -> Wad:
        """Returns the amount of ERC20 token `token` deposited by the specified user.

        Args:
            token: Address of the ERC20 token return the balance of.
            user: Address of the user to check the balance of.

        Returns:
            The ERC20 token `token` balance kept in the IDEX contract by the specified user.
        """
        assert(isinstance(token, Address))
        assert(isinstance(user, Address))
        return Wad(self._contract.call().balanceOf(token.address, user.address))

    def __repr__(self):
        return f"IDEX('{self.address}')"


class IDEXApi:
    """A client for the IDEX API.

    <https://github.com/AuroraDAO/idex-api-docs>

    Attributes:
        idex: The IDEX Exchange contract.
    """
    logger = logging.getLogger()
    timeout = 15.5

    def __init__(self, idex: IDEX, api_server: str, timeout: float):
        assert(isinstance(idex, IDEX))
        assert(isinstance(api_server, str))
        assert(isinstance(timeout, float))

        self.idex = idex
        self.api_server = api_server
        self.timeout = timeout

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_post("/returnTicker", {'market': pair})

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"IDEX API invalid HTTP response: {result.status_code} {result.reason}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"IDEX API invalid JSON response: {result.text}")

        return data

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                          json=params,
                                          timeout=self.timeout))

    def __repr__(self):
        return f"IDEXApi()"
