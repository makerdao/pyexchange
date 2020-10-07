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
import hashlib

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
    def from_our_trades_message(trade: dict, pair: str, base_token: Token, our_liquidity_balance: Wad, previous_base_token_reserves: Wad, timestamp: int) -> Trade:
        """
        Assumptions:
            Prices are denominated in quote token
            Amounts are denominated in the base token

            We are always long the base token, and short quote
            if the amount of TokenA is 0, then we are essentially buying additional base token in exchange for quote token

            If the base token reserves increase compared to the last block, then the trade is a buy

        Uniswap pairs can occasionally differ in base-quote terms from our expectations and price feeds.
        This requires a check to ensure that we are properly comparing asset pairs.
       """
        assert (isinstance(trade, dict))
        assert (isinstance(pair, str))
        assert (isinstance(base_token, Token))
        assert (isinstance(our_liquidity_balance, Wad))
        assert (isinstance(previous_base_token_reserves, Wad))
        assert (isinstance(timestamp, int))

        our_pool_share = our_liquidity_balance / Wad.from_number(trade['totalSupply'])

        if trade['token0']['id'] == base_token.address.address:
            swap_price = Wad.from_number(trade['reserve1']) / Wad.from_number(trade['reserve0'])

            is_sell = Wad.from_number(trade['reserve1']) < previous_base_token_reserves

            amount = our_pool_share * Wad.from_number(trade['volumeToken1'])

        else:
            swap_price = Wad.from_number(trade['reserve0']) / Wad.from_number(trade['reserve1'])

            is_sell = Wad.from_number(trade['reserve0']) < previous_base_token_reserves

            amount = our_pool_share * Wad.from_number(trade['volumeToken0'])

        unhashed_id = str(timestamp)
        trade_id = hashlib.sha256(unhashed_id.encode()).hexdigest()
        return Trade(trade_id=trade_id,
                     timestamp=timestamp,
                     pair=pair,
                     is_sell=is_sell,
                     price=swap_price,
                     amount=amount)

    @staticmethod
    def from_all_trades_message(trade: dict, pair: str, base_token: Token, previous_base_token_reserves: Wad, timestamp: int) -> Trade:
        assert (isinstance(trade, dict))
        assert (isinstance(pair, str))
        assert (isinstance(base_token, Token))
        assert (isinstance(previous_base_token_reserves, Wad))
        assert (isinstance(timestamp, int))

        if trade['token0']['id'] == base_token.address.address:
            swap_price = Wad.from_number(trade['reserve1']) / Wad.from_number(trade['reserve0'])

            is_sell = Wad.from_number(trade['reserve1']) < previous_base_token_reserves

            amount = Wad.from_number(trade['volumeToken1'])

        else:
            swap_price = Wad.from_number(trade['reserve0']) / Wad.from_number(trade['reserve1'])

            is_sell = Wad.from_number(trade['reserve0']) < previous_base_token_reserves

            amount = Wad.from_number(trade['volumeToken0'])

        unhashed_id = str(timestamp)
        trade_id = hashlib.sha256(unhashed_id.encode()).hexdigest()
        return Trade(trade_id=trade_id,
                     timestamp=timestamp,
                     pair=pair,
                     is_sell=is_sell,
                     price=swap_price,
                     amount=amount)

class UniswapV2Analytics(Contract):
    """
    UniswapV2 Graph Protocol Client
    Graph Protocol Explorer is available here: https://thegraph.com/explorer/subgraph/graphprotocol/uniswap
    """

    pair_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Pair.abi')['abi']
    Irouter_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Router02.abi')['abi']
    Ifactory_abi = Contract._load_abi(__name__, 'abi/IUniswapV2Factory.abi')['abi']

    def __init__(self, web3: Web3, token_config_path: str, keeper_address: Address, router_address: Address, factory_address: Address, graph_url: str = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"):
        assert (isinstance(web3, Web3))
        assert (isinstance(token_config_path, str))
        assert (isinstance(keeper_address, Address))
        assert (isinstance(router_address, Address) or router_address is None)
        assert (isinstance(factory_address, Address) or factory_address is None)
        assert (isinstance(graph_url, str))

        self.graph_client = GraphClient(graph_url)

        self.web3 = web3

        self.router_address = router_address
        self.factory_address = factory_address
        self.account_address = keeper_address

        self.our_last_pair_hour_block = 0
        self.all_last_pair_block = 0

        # check to ensure that this isn't a mock instance before attempting to retrieve contracts
        if router_address is not None and factory_address is not None:
            self._router_contract = self._get_contract(web3, self.Irouter_abi, self.router_address)
            self._factory_contract = self._get_contract(web3, self.Ifactory_abi, self.factory_address)

            self.reloadable_config = ReloadableConfig(token_config_path)
            self._last_config_dict = None
            self._last_config = None
            self.token_config = self.get_token_config().token_config

    def get_current_block(self) -> int:
        return int(self.web3.eth.getBlock('latest')['number'])

    # Return our liquidity token balance
    def get_current_liquidity(self, pair_address: Address) -> Wad:
        assert (isinstance(pair_address, Address))

        pair_contract = self._get_contract(self.web3, self.pair_abi, pair_address)

        return Wad(pair_contract.functions.balanceOf(self.account_address.address).call())

    # Return the total number of liquidity tokens minted for a given pair
    def get_total_liquidity(self, pair_address: Address) -> Wad:
        assert (isinstance(pair_address, Address))

        pair_contract = self._get_contract(self.web3, self.pair_abi, pair_address)

        return Wad(pair_contract.functions.totalSupply().call())

    def get_pair_address(self, token_a_address: Address, token_b_address: Address) -> Address:
        assert (isinstance(token_a_address, Address))
        assert (isinstance(token_b_address, Address))

        return Address(self._factory_contract.functions.getPair(token_a_address.address, token_b_address.address).call({"from": self.account_address.address}))

    def get_token_config(self):
        current_config = self.reloadable_config.get_config()
        if current_config != self._last_config_dict:
            self._last_config = TokenConfig(current_config)
            self._last_config_dict = current_config

            self.logger.info(f"Successfully parsed configuration")

        return self._last_config

    def instantiate_tokens(self, pair: str) -> Tuple[Token, Token]:
        assert (isinstance(pair, str))

        def get_address(value) -> Address:
            return Address(value['tokenAddress']) if 'tokenAddress' in value else None

        def get_decimals(value) -> int:
            return value['tokenDecimals'] if 'tokenDecimals' in value else 18

        token_a_name = 'WETH' if pair.split('-')[0] == 'ETH' or pair.split('-')[0] == 'WETH' else pair.split('-')[0]
        token_b_name = 'WETH' if pair.split('-')[1] == 'ETH' or pair.split('-')[1] == 'WETH' else pair.split('-')[1]
        token_a = Token(token_a_name, get_address(self.token_config[token_a_name]), get_decimals(self.token_config[token_a_name]))
        token_b = Token(token_b_name, get_address(self.token_config[token_b_name]), get_decimals(self.token_config[token_b_name]))

        return token_a, token_b

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
                        blockNumber
                    }
                }
            }
        """
        variables = {
            'pair': pair_address.address.lower(),
            'to': self.account_address.address.lower()
        }

        result = self.graph_client.query_request(get_our_burn_txs_query, variables)['burns']

        sorted_burns = sorted(result, key=lambda burn: burn['transaction']['blockNumber'], reverse=True)
        return sorted_burns

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
                        blockNumber
                    }
                    liquidity
                }
            }
        """
        variables = {
            'pair': pair_address.address.lower(),
            'to': self.account_address.address.lower()
        }

        result = self.graph_client.query_request(get_our_mint_txs_query, variables)['mints']

        sorted_mints = sorted(result, key=lambda mint: mint['transaction']['blockNumber'], reverse=True)
        return sorted_mints

    def get_block_trade(self, pair_address: Address, block: int) -> List:
        """
            Retrieve pair data for a given block
        """
        assert (isinstance(pair_address, Address))
        assert (isinstance(block, int))

        get_pair_data_query = """query ($id: Bytes!, $block: Int!)
            {
                pairs (block: {number: $block}, where: {id: $id}) {
                    totalSupply
                    token0 {
                        id
                    }
                    token1 {
                        id
                    }
                    token0Price
                    token1Price
                    volumeToken0
                    volumeToken1
                    reserve0
                    reserve1
                    txCount
                    id
                }
            }
        """
        variables = {
            'id': pair_address.address.lower(),
            'block': block
        }

        result = self.graph_client.query_request(get_pair_data_query, variables)['pairs']
        return result

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        """
            It is assumed that our liquidity in a pool will be added or removed all at once.

            Two stage information retrieval:
                get list of mint events for our address;
                sort the mints, and identify the timestamp for the last mit event.

                If the mint was more than 48 hours ago, return the last 48 hours of data.
                If the mint was less than 48 hours ago, return all data since the mint event.

                When querying, retrieve 49 hours of pair data,
                with the 49th hour used as a starting point for determing sells and buys
                
                All mint events are sorted by descending timestamp.

            Graph Protocol doesn't currently accept queries using Checksum addresses,
            so all addresses must be lowercased prior to submission.
        """
        assert (isinstance(pair, str))
        assert (isinstance(page_number, int))

        trades_list = []

        base_token, quote_token = self.instantiate_tokens(pair)
        pair_address = self.get_pair_address(base_token.address, quote_token.address)

        mint_events = self.get_our_mint_txs(pair_address)
        burn_events = self.get_our_burn_txs(pair_address)

        # calculate starting block, assuming there's 15 seconds in a given block
        current_block = self.get_current_block()
        two_day_ago_block = int(current_block - (4 * 60 * 25))

        if len(mint_events) == 0:
            return trades_list

        last_mint_event = mint_events[0]
        last_mint_block = int(last_mint_event['transaction']['blockNumber'])

        if len(burn_events) != 0:
            last_burn_block = int(burn_events[0]['transaction']['blockNumber'])
        else:
            last_burn_block = None

        our_liquidity_balance = Wad.from_number(last_mint_event['liquidity'])
        current_liquidity = self.get_current_liquidity(pair_address)

        mints_in_last_two_days = list(filter(lambda mint: int(mint['transaction']['blockNumber']) > two_day_ago_block, mint_events))

        if current_liquidity != Wad.from_number(0) and len(mints_in_last_two_days) >= 1:
            start_block = max(self.our_last_pair_hour_block, int(mints_in_last_two_days[-1]['transaction']['blockNumber']))
            end_block = current_block
        elif current_liquidity != Wad.from_number(0) and len(mints_in_last_two_days) == 0:
            start_block = max(self.our_last_pair_hour_block, two_day_ago_block)
            end_block = current_block
        elif current_liquidity == Wad.from_number(0) and len(mints_in_last_two_days) >= 1:
            start_block = max(self.our_last_pair_hour_block, int(mints_in_last_two_days[-1]['transaction']['blockNumber']))
            end_block = last_burn_block if last_burn_block != None else current_block
        else:
            return trades_list

        raw_block_trades = []
        index = 0
        checked_block = start_block
        while checked_block < end_block:
            block_trade = self.get_block_trade(pair_address, checked_block)[0]

            raw_block_trades.append(block_trade)

            if checked_block != start_block:
                if raw_block_trades[index]['token0']['id'] == base_token.address.address:
                    previous_base_token_reserves = Wad.from_number(raw_block_trades[index - 1]['reserve0'])
                else:
                    previous_base_token_reserves = Wad.from_number(raw_block_trades[index - 1]['reserve1'])

                timestamp = self.web3.eth.getBlock(checked_block).timestamp

                trades_list.append(UniswapTrade.from_our_trades_message(block_trade, pair, base_token, our_liquidity_balance, previous_base_token_reserves, timestamp))

            # assume there's 240 blocks in an hour
            checked_block += 240
            index += 1

        # Avoid excessively querying the api by storing the block of the last retrieved trade
        if len(trades_list) > 0:
            self.our_last_pair_hour_block = end_block

        return trades_list

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert (isinstance(pair, str))
        assert (isinstance(page_number, int))

        base_token, quote_token = self.instantiate_tokens(pair)
        pair_address = self.get_pair_address(base_token.address, quote_token.address)

        trades_list = []

        # calculate starting block, assuming there's 15 seconds in a given block
        current_block = self.get_current_block()
        two_day_ago_block = int(current_block - (4 * 60 * 25))

        start_block = two_day_ago_block if two_day_ago_block > self.all_last_pair_block else self.all_last_pair_block
        end_block = current_block

        raw_block_trades = []
        index = 0
        checked_block = start_block
        while checked_block < end_block:
            block_trade = self.get_block_trade(pair_address, checked_block)[0]

            raw_block_trades.append(block_trade)

            if checked_block != start_block:
                if raw_block_trades[index]['token0']['id'] == base_token.address.address:
                    previous_base_token_reserves = Wad.from_number(raw_block_trades[index - 1]['reserve0'])
                else:
                    previous_base_token_reserves = Wad.from_number(raw_block_trades[index - 1]['reserve1'])

                timestamp = self.web3.eth.getBlock(checked_block).timestamp

                trades_list.append(UniswapTrade.from_all_trades_message(block_trade, pair, base_token, previous_base_token_reserves, timestamp))

            # assume there's 240 blocks in an hour
            checked_block += 240
            index += 1

        # Avoid excessively querying the api by storing the timestamp of the last retrieved trade
        if len(trades_list) > 0:
            self.all_last_pair_block = end_block

        return trades_list

    def _deadline(self) -> int:
        """Get a predefined deadline."""
        return int(time.time()) + 1000

    def __eq__(self, other):
        assert (isinstance(other, UniswapExchange))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapV2Analytics"
