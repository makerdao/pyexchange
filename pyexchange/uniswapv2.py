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

import time
from web3 import Web3
from typing import List

from pymaker import Contract, Address, Transact, Wad
from pymaker.token import ERC20Token
from pymaker.model import Token
from pymaker.approval import directly
from pyexchange.graph import GraphClient
from pyexchange.model import Trade


class UniswapV2(Contract):
    """
    UniswapV2 Python Client

    Each UniswapV2 instance is intended to be used with a single pool at a time.

    Documentation is available here: https://uniswap.org/docs/v2/
    """

    pair_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Pair.abi')
    router_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Router02.abi')
    factory_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Factory.abi')
    router_bin = Contract._load_bin(__name__, 'abi/IUniswapV2Router02.bin')
    factory_bin = Contract._load_bin(__name__, 'abi/IUniswapV2Factory.bin')

    def __init__(self, web3: Web3, token_a: Token, token_b: Token):
                 # ec_signature_r: Optional[str], ec_signature_s: Optional[str], ec_signature_v: Optional[int]):
        assert (isinstance(web3, Web3))
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))

        self.web3 = web3
        self.token_a = token_a
        self.token_b = token_b
        self.router_address = Address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
        self.factory_address = Address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")
        self._router_contract = self._get_contract(web3, self.router_abi['abi'], self.router_address)
        self._factory_contract = self._get_contract(web3, self.factory_abi['abi'], self.factory_address)

        self.pair_address = self.get_pair_address(self.token_a.address, self.token_b.address)
        self.is_new_pool = self.pair_address == Address("0x0000000000000000000000000000000000000000")
        if not self.is_new_pool:
            self.set_and_approve_pair_token(self.pair_address)

        self.account_address = Address(self.web3.eth.defaultAccount)

        #     TODO: Add permit support
        # self.ec_signature_r = ec_signature_r
            # self.ec_signature_s = ec_signature_s
            # self.ec_signature_v = ec_signature_v

    def set_and_approve_pair_token(self, pair_address: Address):
        self._pair_contract = self._get_contract(self.web3, self.pair_abi['abi'], pair_address)
        self.pair_token = Token('Liquidity', pair_address, 18)
        self.approve(self.pair_token)

    def get_account_token_balance(self, token: Token) -> Wad:
        assert (isinstance(token, Token))

        return token.normalize_amount(ERC20Token(web3=self.web3, address=token.address).balance_of(self.account_address))

    def get_account_eth_balance(self) -> Wad:
        return Wad.from_number(Web3.fromWei(self.web3.eth.getBalance(self.account_address.address), 'ether'))

    def get_exchange_balance(self, token: Token, pair_address: Address) -> Wad:
        assert (isinstance(token, Token))
        assert (isinstance(pair_address, Address))

        return token.normalize_amount(ERC20Token(web3=self.web3, address=token.address).balance_of(pair_address))

    # retrieve exchange rate for the instance's pair token
    def get_exchange_rate(self) -> Wad:
        pair_address = self.get_pair_address(self.token_a.address, self.token_b.address)

        token_a_reserve = self.get_exchange_balance(self.token_a, pair_address)
        token_b_reserve = self.get_exchange_balance(self.token_b, pair_address)

        return token_a_reserve / token_b_reserve

    # Return the total number of liquidity tokens minted for a given pair
    def get_total_liquidity(self) -> Wad:
        return Wad(self._pair_contract.functions.totalSupply().call())

    # Return our liquidity token balance
    def get_current_liquidity(self) -> Wad:
        return Wad(self._pair_contract.functions.balanceOf(self.account_address.address).call())

    # Return a pools minimum liquidity token balance
    def get_minimum_liquidity(self) -> Wad:
        return Wad(self._pair_contract.functions.MINIMUM_LIQUIDITY(self.account_address.address).call())

    def get_pair_address(self, token_a_address: Address, token_b_address: Address) -> Address:
        assert (isinstance(token_a_address, Address))
        assert (isinstance(token_b_address, Address))

        return Address(self._factory_contract.functions.getPair(token_a_address.address, token_b_address.address).call())

    # TODO: determine appropriate amount default
    def approve(self, token: Token, amount: int = 10):
        assert (isinstance(token, Token))
        assert (isinstance(amount, int))

        erc20_token = ERC20Token(self.web3, token.address)

        approval_function = directly()
        return approval_function(erc20_token, self.router_address, 'IUniswapV2Router02')

    def get_block(self) -> Transact:
        return self.web3.eth.getBlock('latest')['number']

    def get_amounts_out(self, amount_in: Wad, tokens: List[Token]) -> List[Wad]:
        """ Calculate maximum output amount of a given input.

        Desired amount_in must be less than available liquidity or call will fail.

        Args:
            amounts_in: Desired amount of tokens out.
            tokens: List of tokens used to form a path for swap and normalize amounts for token decimals
        Returns:
            A list of uint256 reserve amounts required.
        """
        assert (isinstance(amount_in, Wad))
        assert (isinstance(tokens, List))

        token_addresses = list(map(lambda token: token.address.address, tokens))
        amounts = self._router_contract.functions.getAmountsOut(amount_in.value, token_addresses).call()
        wad_amounts = list(map(lambda amount: Wad.from_number(Web3.fromWei(amount, 'ether')), amounts))

        for index, token in enumerate(tokens):
            wad_amounts[index] = token.normalize_amount(wad_amounts[index])

        return wad_amounts

    def get_amounts_in(self, amount_out: Wad, path: List) -> List[Wad]:
        """ Calculate amount of given inputs to achieve an exact output amount.
        
        Desired amount_out must be less than available liquidity or call will fail.

        Args:
            amount_out: Desired amount of tokens out.
            path: List of addresses used to form a path for swap 
        Returns:
            A list of uint256 reserve amounts required.
        """
        assert (isinstance(amount_out, Wad))
        assert (isinstance(path, List))

        amounts = self._router_contract.functions.getAmountsIn(amount_out.value, path).call()
        return list(map(lambda amount: Wad.from_number(Web3.fromWei(amount, 'ether')), amounts))

    def add_liquidity(self, amounts: dict, token_a: Token, token_b: Token) -> Transact:
        """ Add liquidity to arbitrary token pair.

        Args:
            amounts: dictionary[Wad, Wad, Wad, Wad]
            token_a: First token in the pool
            token_b: Second token in the pool
        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert (isinstance(amounts, dict))
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))

        addLiquidityArgs = [
            token_a.address.address,
            token_b.address.address,
            amounts['amount_a_desired'].value,
            amounts['amount_b_desired'].value,
            amounts['amount_a_min'].value,
            amounts['amount_b_min'].value,
            self.account_address.address,
            self._deadline()
        ]

        return Transact(self, self.web3, self.router_abi['abi'], self.router_address, self._router_contract,
                        'addLiquidity', addLiquidityArgs)

    def add_liquidity_eth(self, amounts: dict, token: Token) -> Transact:
        """ Add liquidity to token-weth pair.

        Args:
            amounts: dictionary[Wad, Wad, Wad, Wad]
            token_a: Token side of the pool
        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert (isinstance(amounts, dict))
        assert (isinstance(token, Token))

        addLiquidityArgs = [
            token.address.address,
            amounts['amount_token_desired'].value,
            amounts['amount_token_min'].value,
            amounts['amount_eth_min'].value,
            self.account_address.address,
            self._deadline()
        ]

        return Transact(self, self.web3, self.router_abi['abi'], self.router_address, self._router_contract,
                        'addLiquidityETH', addLiquidityArgs, {'value': amounts['amount_eth_desired'].value})

    # TODO: finish implementing
    # Enable liquidity to be removed from a pool up to a set limit
    def permit_removal(self, pair, amount: Wad) -> Transact:
        pass

    def remove_liquidity(self, amounts: dict, token_a: Token, token_b: Token) -> Transact:
        """ Remove liquidity from arbitrary token pair.

        Args:
            token_a: Address of pool token A.
            token_b: Address of pool token B.
            amounts: dictionary[uint256, uint256, uint256]
        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))
        assert (isinstance(amounts, dict))

        removeLiquidityArgs = [
            token_a.address.address,
            token_b.address.address,
            amounts['liquidity'].value,
            amounts['amountAMin'].value,
            amounts['amountBMin'].value,
            self.account_address.address,
            self._deadline()
        ]

        return Transact(self, self.web3, self.router_abi['abi'], self.router_address, self._router_contract,
                        'removeLiquidity', removeLiquidityArgs)

    # TODO: add switch to handle whether or not a givne pool charges a fee
    # If so, use ternary to change invoked method name
    def remove_liquidity_eth(self, amounts: dict, token: Token):
        """ Remove liquidity from token-weth pair.

        Args:
            token_a: Address of pool token.
            amounts: dictionary[uint256, uint256, uint256]
        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert (isinstance(amounts, dict))
        assert (isinstance(token, Token))

        removeLiquidityArgs = [
            token.address.address,
            amounts['liquidity'].value,
            amounts['amountTokenMin'].value,
            amounts['amountETHMin'].value,
            self.account_address.address,
            self._deadline()
        ]

        return Transact(self, self.web3, self.router_abi['abi'], self.router_address, self._router_contract,
                        'removeLiquidityETH', removeLiquidityArgs)

    def swap_exact_eth_for_tokens(self, eth_to_swap: Wad, min_amount_out: Wad, path: List) -> Transact:
        """Convert ETH to Tokens.

        Requires Approval to have already been called on the token to swap

        Args:
            eth_to_swap: Amount of ETH to swap for token.
            min_amount_out: Minimum amount of output token to set price
            path: array of token addresses used to form swap route
        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert (isinstance(eth_to_swap, Wad))
        assert (isinstance(min_amount_out, Wad))
        assert (isinstance(path, List))

        swapArgs = [
            min_amount_out.value,
            path,
            self.account_address.address,
            self._deadline()
        ]

        return Transact(self, self.web3, self.router_abi['abi'], self.router_address, self._router_contract,
                        'swapExactETHForTokens', swapArgs, {'value': eth_to_swap.value})

    def swap_exact_tokens_for_tokens(self, tokens_to_swap: Wad, min_amount_out: Wad, path: List) -> Transact:
        """Convert ERC20 to ERC20.

        Requires Approval to have already been called on the token to swap

        Args:
            tokens_to_swap: Amount of given token to swap for token.
            min_amount_out: Minimum amount of output token to set price
            path: array of token addresses used to form swap route
        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert (isinstance(tokens_to_swap, Wad))
        assert (isinstance(min_amount_out, Wad))
        assert (isinstance(path, List))

        swapArgs = [
            tokens_to_swap,
            min_amount_out,
            path,
            self.account_address.address,
            self._deadline()
        ]

        return Transact(self, self.web3, self.router_abi['abi'], self.router_address, self._router_contract,
                        'swapExactTokensForTokens', swapArgs)

    def _deadline(self):
        """Get a predefined deadline."""
        return int(time.time()) + 1000

    def __eq__(self, other):
        assert (isinstance(other, UniswapExchange))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapV2"
