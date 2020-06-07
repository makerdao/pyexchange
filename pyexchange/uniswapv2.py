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

from pymaker import Contract, Address, Transact, Wad
from pymaker.token import ERC20Token

from typing import List

from pyexchange.graph import GraphClient
from pyexchange.model import Pair, Trade


class UniswapTrade(Trade):
    @staticmethod
    def from_message(item):
        return Trade(trade_id=item['oid'],
                     timestamp=item['created_at'],
                     pair=item['book'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['amount']))


class UniswapV2(Contract):

    pair_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Pair.abi')
    router_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Router02.abi')
    factory_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Factory.abi')

    def __init__(self, web3: Web3, graph_url: str, pair: Address, router: Address, factory):
        assert (isinstance(web3, Web3))
        assert (isinstance(graph_url, str))
        assert (isinstance(pair, Address))
        assert (isinstance(router, Address))

        self.web3 = web3
        self.pair = pair
        self.router = router
        # self.token = ERC20Token(web3=web3, address=token)
        self._pair_contract = self._get_contract(web3, self.pair_abi, pair)
        self._router_contract = self._get_contract(web3, self.router_abi, router)
        self._factory_contract = self._get_contract(web3, self.factory_contract, factory)
        self.account_address = Address(self.web3.eth.defaultAccount)
        self.graph_client = GraphClient(graph_url)

    def get_account_token_balance(self):
        return self.token.balance_of(self.account_address)

    def get_exchange_balance(self):
        return self.token.balance_of(self.exchange)

    def get_markets(self) -> dict:
        query = '''
        {
            pairs {
                totalSupply
                id
                token0 {
                  name
                  id
                }
                token1 {
                  name
                  id
                }
            }
        }
        '''
        result = self.graph_client.query_request(query, None)
        return result['data']

    # TODO: check against token address
    # TODO: Need to add support for tokens to pyexchange
    def _is_pair(self, pair_to_check, desired_pair) -> bool:
        name0 = desired_pair.split()[0]
        name1 = desired_pair.split()[0]

        if name0 == "ETH":
            name0 = 'Wrapped Ether'

        if name0 == "DAI":
            name0 = 'Wrapped Ether'
        # if pair_to_check['token0']['id'] =

    def get_pair(self, pair) -> dict:
        return filter(lambda p: self._is_pair(p, pair), self.get_markets()['pairs'])[0]

    # return the current balance in a given pool
    def get_balances(self) -> dict:
        query = '''query ($user: ID!)
            {
              liquidityPositions(where: {user: $user}) {
                id
                liquidityTokenBalance
                poolOwnership
              }
            }
        '''
        variables = {
            'user': self.account_address
        }

        result = self.graph_client.query_request(query, variables)
        return result['data']

    # filter contract events for an address to focus on swaps
    def get_trades(self, pair: Pair) -> List[Trade]:
        query = '''query ($address: ID!)
        {
          swaps(where: {id: $address}) {
            id
            sender
            pair {
              id
            }
            amountUSD
            amount0In
            amount1In
            amount0Out
            amount1Out
            timestamp
            logIndex
          }
        }
        '''
        variables = {
            'address': self.account_address
        }

        result = self.graph_client.query_request(query, variables)
        return list(map(lambda swap: UniswapTrade.from_message(swap), result['data']['swaps']))

    # TODO: use periphery library for pricing
    # def get_exchange_rate(self):
    #     eth_reserve = self.get_eth_exchange_balance()
    #     token_reserve = self.get_exchange_balance()
    #     return token_reserve / eth_reserve

    def get_eth_token_input_price(self, amount: Wad):
        assert (isinstance(amount, Wad))

        return Wad(self._contract.functions.getEthToTokenInputPrice(amount.value).call())

    def get_token_eth_input_price(self, amount: Wad):
        assert (isinstance(amount, Wad))

        return Wad(self._contract.functions.getTokenToEthInputPrice(amount.value).call())

    def get_eth_token_output_price(self, amount: Wad):
        assert (isinstance(amount, Wad))

        return Wad(self._contract.functions.getEthToTokenOutputPrice(amount.value).call())

    def get_token_eth_output_price(self, amount: Wad):
        assert (isinstance(amount, Wad))

        return Wad(self._contract.functions.getTokenToEthOutputPrice(amount.value).call())

    def get_current_liquidity(self):
        return Wad(self._contract.functions.balanceOf(self.account_address.address).call())

    def get_minimum_liquidity(self):
        return Wad(self._contract.functions.MINIMUM_LIQUIDITY(self.account_address.address).call())

    # TODO: finish implementing with CREATE2
    # Factory contract exposes a getPair method that can also be called offchain with CREATE2 to save gas
    def get_pair_address(self, token1: Address, token2: Address) -> Address:
        return Address(self._factory_contract.functions.getPair(token1, token2).call())

    def add_liquidity(self, amounts: dict, token_a: Address, token_b: Address) -> Transact:
        assert (isinstance(amounts, dict))

        # min_liquidity = Wad.from_number(0.5) * amount
        # max_token = amount * self.get_exchange_rate() * Wad.from_number(1.00000001)

        pairAddress = self.get_pair_address(token_a, token_b)

        addLiquidityArgs = [
            token_a,
            token_b,
            amounts['amount_a_desired'],
            amounts['amount_b_desired'],
            amounts['amount_a_min'],
            amounts['amount_b_min'],
            pairAddress,
            self._deadline()
        ]

        return Transact(self, self.web3, self.router_abi, self.router, self._router_contract,
                        'addLiquidity', addLiquidityArgs)

    def remove_liquidity(self, amount: Wad) -> Transact:
        assert (isinstance(amount, Wad))

        removeLiquidityArgs = [
            amount.value, 1, 1, self._deadline()
        ]

        return Transact(self, self.web3, self.abi, self.exchange, self._contract,
                        'removeLiquidity', removeLiquidityArgs)

    def eth_to_token_swap_input(self, eth_sold: Wad) -> Transact:
        """Convert ETH to Tokens.

        Args:
            eth_sold: Amount of ETH to swap for token.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        return Transact(self, self.web3, self.abi, self.exchange, self._contract,
                        'ethToTokenSwapInput', [1, self._deadline()], {'value': eth_sold.value})

    def token_to_eth_swap_input(self, tokens_sold: Wad) -> Transact:
        """Convert Tokens to ETH.

        Args:
            eth_sold: Amount of token to swap for ETH.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        return Transact(self, self.web3, self.abi, self.exchange, self._contract,
                        'tokenToEthSwapInput', [tokens_sold.value, 1, self._deadline()])

    def _deadline(self):
        """Get a predefined deadline."""
        return int(time.time()) + 1000

    def __eq__(self, other):
        assert (isinstance(other, UniswapExchange))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapExchange('{self.exchange}')"
