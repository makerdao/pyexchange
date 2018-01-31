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

from web3 import Web3

from pymaker import Contract, Address, Transact
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
        """Approve the IKEX Exchange contract to fully access balances of specified tokens.

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

    def __init__(self, idex: IDEX, api_server: str):
        assert(isinstance(idex, IDEX))
        assert(isinstance(api_server, str))

        self.idex = idex
        self.api_server = api_server

    def __repr__(self):
        return f"IDEXApi()"
