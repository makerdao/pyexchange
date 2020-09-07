# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 grandizzy
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

import time
from web3 import Web3

from pyflex import Contract, Address, Transact, Wad
from pyflex.token import ERC20Token


class Uniswap(Contract):
    abi = Contract._load_abi(__name__, 'abi/UNISWAP.abi')

    def __init__(self, web3: Web3, token: Address, exchange: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(token, Address))
        assert(isinstance(exchange, Address))

        self.web3 = web3
        self.exchange = exchange
        self.token = ERC20Token(web3=web3, address=token)
        self._contract = self._get_contract(web3, self.abi, exchange)
        self.account_address = Address(self.web3.eth.defaultAccount)

    def get_account_token_balance(self):
        return self.token.balance_of(self.account_address)

    def get_account_eth_balance(self):
        return Wad(self.web3.eth.getBalance(self.account_address.address))

    def get_exchange_balance(self):
        return self.token.balance_of(self.exchange)

    def get_eth_exchange_balance(self):
        return Wad(self.web3.eth.getBalance(self.exchange.address))

    def get_exchange_rate(self):
        eth_reserve = self.get_eth_exchange_balance()
        token_reserve = self.get_exchange_balance()
        return token_reserve / eth_reserve

    def get_eth_token_input_price(self, amount: Wad):
        assert(isinstance(amount, Wad))

        return Wad(self._contract.functions.getEthToTokenInputPrice(amount.value).call())

    def get_token_eth_input_price(self, amount: Wad):
        assert(isinstance(amount, Wad))

        return Wad(self._contract.functions.getTokenToEthInputPrice(amount.value).call())

    def get_eth_token_output_price(self, amount: Wad):
        assert(isinstance(amount, Wad))

        return Wad(self._contract.functions.getEthToTokenOutputPrice(amount.value).call())

    def get_token_eth_output_price(self, amount: Wad):
        assert(isinstance(amount, Wad))

        return Wad(self._contract.functions.getTokenToEthOutputPrice(amount.value).call())

    def get_current_liquidity(self):
        return Wad(self._contract.functions.balanceOf(self.account_address.address).call())

    def add_liquidity(self, amount: Wad) -> Transact:
        assert(isinstance(amount, Wad))

        min_liquidity = Wad.from_number(0.5) * amount
        max_token = amount * self.get_exchange_rate() * Wad.from_number(1.00000001)

        return Transact(self, self.web3, self.abi, self.exchange, self._contract,
                        'addLiquidity', [min_liquidity.value, max_token.value, self._deadline()],
                        {'value': amount.value})

    def remove_liquidity(self, amount: Wad) -> Transact:
        assert(isinstance(amount, Wad))

        return Transact(self, self.web3, self.abi, self.exchange, self._contract,
                        'removeLiquidity', [amount.value, 1, 1, self._deadline()])

    def eth_to_token_swap_input(self, eth_sold: Wad) -> Transact:
        """Convert ETH to Tokens.

        Args:
            eth_sold: Amount of ETH to swap for token.

        Returns:
            A :py:class:`pyflex.Transact` instance, which can be used to trigger the transaction.
        """
        return Transact(self, self.web3, self.abi, self.exchange, self._contract,
                        'ethToTokenSwapInput', [1, self._deadline()], {'value': eth_sold.value})

    def token_to_eth_swap_input(self, tokens_sold: Wad) -> Transact:
        """Convert Tokens to ETH.

        Args:
            eth_sold: Amount of token to swap for ETH.

        Returns:
            A :py:class:`pyflex.Transact` instance, which can be used to trigger the transaction.
        """
        return Transact(self, self.web3, self.abi, self.exchange, self._contract,
                        'tokenToEthSwapInput', [tokens_sold.value, 1, self._deadline()])

    def _deadline(self):
        """Get a predefined deadline."""
        return int(time.time()) + 1000

    def __eq__(self, other):
        assert(isinstance(other, UniswapExchange))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapExchange('{self.exchange}')"

