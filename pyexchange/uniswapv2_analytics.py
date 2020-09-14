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
from typing import List, Tuple

from pymaker import Contract, Address, Transact, Wad
from pymaker.reloadable_config import ReloadableConfig
from pymaker.token import ERC20Token
from pymaker.util import http_response_summary
from pymaker.model import Token, TokenConfig
from pymaker.approval import directly
from pyexchange.graph import GraphClient
from pyexchange.model import Trade


class UniswapTrade(Trade):

    @staticmethod
    def from_message(trade: dict, pair: str, token_a: Token, token_b: Token) -> Trade:
        """
        Assumptions:
            Prices are denominated in quote token
            Aounts are denominated in the base token

            We are always long the base token, and short quote
            if the amount of TokenA is 0, then we are essentially buying additional base token in exchange for quote token

        Uniswap pairs can occasionally differ in base-quote terms from our expectations and price feeds.
        This requires a check to ensure that we are properly comparing asset pairs.
       """
        assert (isinstance(trade, dict))
        assert (isinstance(pair, str))
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))

        if trade['pair']['token0']['id'] == token_a.address.address:
            swap_price = Wad.from_number(trade['pair']['token1Price'])

            is_sell = trade['amount0In'] != '0'

            if is_sell:
                amount = Wad.from_number(trade['amount1Out']) / Wad.from_number(trade['pair']['token1Price'])
            else:
                amount = Wad.from_number(trade['amount0Out'])

        else:
            swap_price = Wad.from_number(trade['pair']['token0Price'])

            is_sell = trade['amount1In'] != "0"

            if is_sell:
                amount = Wad.from_number(trade['amount0Out']) / Wad.from_number(trade['pair']['token0Price'])
            else:
                amount = Wad.from_number(trade['amount1Out'])

        return Trade(trade_id=trade['id'],
                     timestamp=int(trade['timestamp']),
                     pair=pair,
                     is_sell=is_sell,
                     price=swap_price,
                     amount=amount)


class UniswapV2Analytics(Contract):
    """
    UniswapV2 Python Client

    Each UniswapV2 instance is intended to be used with a single pool at a time.

    Documentation is available here: https://uniswap.org/docs/v2/
    """

    pair_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Pair.abi')
    Irouter_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Router02.abi')['abi']
    router_abi = Contract._load_abi(__name__, 'abi/UniswapV2Router02.abi')
    Ifactory_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Factory.abi')['abi']
    factory_abi = Contract._load_abi(__name__, 'abi/UniswapV2Factory.abi')

    def __init__(self, web3: Web3, token_config_path: str, keeper_address: Address, router_address: Address, factory_address: Address, graph_url: str = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"):
        assert (isinstance(web3, Web3))
        assert (isinstance(token_config_path, str))
        assert (isinstance(keeper_address, Address))
        assert (isinstance(router_address, Address))
        assert (isinstance(factory_address, Address))
        assert (isinstance(graph_url, str))

        self.graph_client = GraphClient(graph_url)

        self.web3 = web3

        self.router_address = router_address
        self.factory_address = factory_address
        self._router_contract = self._get_contract(web3, self.Irouter_abi, self.router_address)
        self._factory_contract = self._get_contract(web3, self.Ifactory_abi, self.factory_address)

        self.account_address = keeper_address

        self.reloadable_config = ReloadableConfig(token_config_path)
        self._last_config_dict = None
        self._last_config = None
        self.token_config = self.get_token_config().tokens

        self.last_mint_timestamp = Wad.from_number(0)
        
    def get_account_token_balance(self, token: Token) -> Wad:
        assert (isinstance(token, Token))

        return token.normalize_amount(ERC20Token(web3=self.web3, address=token.address).balance_of(self.account_address))

    def get_account_eth_balance(self) -> Wad:
        return Wad.from_number(Web3.fromWei(self.web3.eth.getBalance(self.account_address.address), 'ether'))

    def get_exchange_balance(self, token: Token, pair_address: Address) -> Wad:
        assert (isinstance(token, Token))
        assert (isinstance(pair_address, Address))

        return token.normalize_amount(ERC20Token(web3=self.web3, address=token.address).balance_of(pair_address))

    def get_our_exchange_balance(self, token: Token, pair_address: Address) -> Wad:
        assert (isinstance(token, Token))
        assert (isinstance(pair_address, Address))

        current_liquidity = self.get_current_liquidity()
        if current_liquidity == Wad.from_number(0):
            return Wad.from_number(0)

        total_liquidity = self.get_total_liquidity()
        exchange_balance = self.get_exchange_balance(token, pair_address)

        return current_liquidity * exchange_balance / total_liquidity

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

        return Address(self._factory_contract.functions.getPair(token_a_address.address, token_b_address.address).call({"from": self.account_address.address}))

    def approve(self, token: Token):
        assert (isinstance(token, Token))

        erc20_token = ERC20Token(self.web3, token.address)

        approval_function = directly()
        return approval_function(erc20_token, self.router_address, 'UniswapV2Router02')

    def get_token_config(self):
        current_config = self.reloadable_config.get_config()
        if current_config != self._last_config_dict:
            self._last_config = TokenConfig(current_config)
            self._last_config_dict = current_config

            self.logger.info(f"Successfully parsed configuration")

        return self._last_config

    def instantiate_tokens(self, pair: str) -> Tuple[Token, Token]:
        assert (isinstance(pair, str))

        token_a_name = 'WETH' if pair.split('-')[0] == 'ETH' or pair.split('-')[0] == 'WETH' else pair.split('-')[0]
        token_b_name = 'WETH' if pair.split('-')[1] == 'ETH' or pair.split('-')[1] == 'WETH' else pair.split('-')[1]
        token_a = list(filter(lambda token: token.name == token_a_name, self.token_config))[0]
        token_b = list(filter(lambda token: token.name == token_b_name, self.token_config))[0]

        return token_a, token_b

    def get_our_mint_txs(self, pair_address: Address) -> dict:
        assert (isinstance(pair_address, Address))

        get_our_mint_txs_query = """query ($pair: Bytes!, $to: Bytes!)
            {
                mints (where: {pair: $pair, to: $to}) {
                    amount0
                    amount1
                    id
                    to
                    sender
                    timestamp
                    pair {
                        id
                        token0 {
                            id
                        }
                        token1 {
                            id
                        }
                    }
                    transaction {
                        id
                    }
                }
            }
        """
        variables = {
            'pair': pair_address.address.lower(),
            'to': self.account_address.address.lower()
        }

        result = self.graph_client.query_request(get_our_mint_txs_query, variables)['mints']

        sorted_mints = sorted(result, key=lambda mint: mint['timestamp'], reverse=True)
        return sorted_mints

    def get_our_burn_txs(self, pair_address: Address) -> List:
        assert (isinstance(pair_address, Address))

        get_our_burn_txs_query = """query ($pair: Bytes!, $to: Bytes!)
            {
                burns (where: {pair: $pair, to: $to}) {
                    id
                    to
                    timestamp
                    pair {
                        id
                        token0 {
                            id
                        }
                        token1 {
                            id
                        }
                    }
                    transaction {
                        id
                    }
                }
            }
        """
        variables = {
            'pair': pair_address.address.lower(),
            'to': self.account_address.address.lower()
        }

        result = self.graph_client.query_request(get_our_burn_txs_query, variables)['burns']

        sorted_burns = sorted(result, key=lambda burn: burn['timestamp'], reverse=True)
        return sorted_burns

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        """
            It is assumed that our liquidity in a pool will be added or removed all at once.

            Two stage information retrieval:
                get list mint and burn events for our address;
                get a list of mint and burn transaction timestamps for each pair;
                append set of swaps for the pair between timestamps to larger list of trades

            Graph Protocol doesn't currently accept queries using Checksum addresses,
            so all addresses must be lowercased prior to submission.

            Check to see if we've already retrieved the list of timestamps to avoid overloading Graph node
        """
        assert (isinstance(pair, str))
        assert (isinstance(page_number, int))

        token_a, token_b = self.instantiate_tokens(pair)

        pair_address = self.get_pair_address(token_a.address, token_b.address)

        mint_events = self.get_our_mint_txs(pair_address)
        burn_events = self.get_our_burn_txs(pair_address)

        number_of_mints = len(mint_events)
        number_of_burns = len(burn_events)

        trades_list = []

        # construct an object of symmetric mint and burn events and append to list of events to iterate over
        liquidity_events = {
            'mints': mint_events,
            'burns': burn_events
        }

        if self.last_mint_timestamp == Wad.from_number(mint_events[-1]['timestamp']):
            return trades_list

        # iterate between each pair of mint and burn timestamps to query all swaps between those events
        # if there's unbalance mints and burns, assume we've added but not removed liquidity, and set less than value to current timestamp
        for index, mint  in enumerate(liquidity_events['mints']):
            mint_timestamp = mint['timestamp']
            burn_timestamp = liquidity_events['burns'][index] if number_of_mints == number_of_burns else int(time.time())

            get_swaps_query = """query ($pair: Bytes!, $timestamp_mint: BigInt!, $timestamp_burn: BigInt!)
            {
                swaps(where: {pair: $pair, timestamp_gte: $timestamp_mint, timestamp_lte: $timestamp_burn}) {
                    id
                    pair {
                        id
                        token0 {
                            id
                        }
                        token1 {
                            id
                        }
                        totalSupply
                        reserve0
                        reserve1
                        token0Price
                        token1Price
                    }
                    transaction {
                        id
                    }
                    timestamp
                    amount0In
                    amount1In
                    amount0Out
                    amount1Out
                }
            }
            """
            variables = {
                'pair': pair_address.address.lower(),
                'timestamp_mint': mint_timestamp,
                'timestamp_burn': burn_timestamp
            }

            result = self.graph_client.query_request(get_swaps_query, variables)
            swaps_list = result['swaps']

            trades = list(map(lambda item: UniswapTrade.from_message(item, pair, token_a, token_b), swaps_list))
            trades_list.extend(trades)

        self.last_mint_timestamp = Wad.from_number(mint_events[-1]['timestamp'])

        return trades_list

    def get_all_trades(self, pair: str, page_number: int=1) -> List[Trade]:
        """
        """
        assert (isinstance(pair, str))
        assert (isinstance(page_number, int))

        token_a, token_b = self.instantiate_tokens(pair)

        get_swaps_query = """query ($pair: Bytes!)
        {
            swaps(where: {pair: $pair}) {
                id
                pair {
                    id
                    token0 {
                        id
                    }
                    token1 {
                        id
                    }
                    totalSupply
                    reserve0
                    reserve1
                    token0Price
                    token1Price
                }
                transaction {
                    id
                }
                timestamp
                amount0In
                amount1In
                amount0Out
                amount1Out
            }
        }
        """
        variables = {
            'pair': pair_address.address.lower()
        }

        result = self.graph_client.query_request(get_swaps_query, variables)
        swaps_list = result['swaps']

        trades = list(map(lambda item: UniswapTrade.from_message(item, pair, token_a, token_b), swaps_list))
        return trades

    def _deadline(self) -> int:
        """Get a predefined deadline."""
        return int(time.time()) + 1000

    def __eq__(self, other):
        assert (isinstance(other, UniswapExchange))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapV2Analytics"
