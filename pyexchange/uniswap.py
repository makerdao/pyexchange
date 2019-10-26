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
from hexbytes import HexBytes
from pprint import pformat
from typing import List
from web3 import Web3
from web3.utils.events import get_event_data

from pymaker import Contract, Address, Transact, Wad
from pymaker.token import ERC20Token


class PurchaseEvent:
    """Handles TokenPurchase and EthPurchase contract events"""
    def __init__(self, event_data, tx_hash, timestamp):
        args = event_data.args
        self.buyer = Address(args.buyer)
        self.tx_hash = tx_hash
        self.timestamp = timestamp

        # from TokenPurchase event
        if 'eth_sold' in args:
            self.eth_sold = Wad(args.eth_sold)
            self.tokens_bought = Wad(args.tokens_bought)
            self.tokens_sold = None
            self.eth_bought = None

        # from EthPurchase event
        if 'tokens_sold' in args:
            self.tokens_sold = Wad(args.tokens_sold)
            self.eth_bought = Wad(args.eth_bought)
            self.eth_sold = None
            self.tokens_bought = None

    @classmethod
    def from_event(cls, event: dict, contract_abi: list, web3: Web3):
        assert(isinstance(event, dict))
        assert(isinstance(contract_abi, list))
        topics = event.get('topics')
        assert(topics)

        tx_hash = event.get('transactionHash').hex()
        block = event.get('blockNumber')
        timestamp = web3.eth.getBlock(block).timestamp
        if topics[0] == HexBytes('0xcd60aa75dea3072fbc07ae6d7d856b5dc5f4eee88854f5b4abf7b680ef8bc50f'):
            event_abi = [abi for abi in contract_abi if abi.get('name') == 'TokenPurchase'][0]
            event_data = get_event_data(event_abi, event)
            return PurchaseEvent(event_data, tx_hash, timestamp)
        elif topics[0] == HexBytes('0x7f4091b46c33e918a0f3aa42307641d17bb67029427a5369e54b353984238705'):
            event_abi = [abi for abi in contract_abi if abi.get('name') == 'EthPurchase'][0]
            event_data = get_event_data(event_abi, event)
            return PurchaseEvent(event_data, tx_hash, timestamp)
        else:
            raise ValueError(f"unknown event {event}")

    def __repr__(self):
        return pformat(vars(self))


class Trade:
    def __init__(self, event: PurchaseEvent, symbol: str):
        assert(isinstance(event, PurchaseEvent))
        assert(isinstance(symbol, str))

        self.trade_id = event.tx_hash
        self.timestamp = event.timestamp
        self.pair = f"{symbol}-ETH"

        if event.tokens_sold is None:
            self.is_sell = False
            self.price = event.eth_sold / event.tokens_bought
            self.amount = event.tokens_bought
        elif event.tokens_bought is None:
            self.is_sell = True
            self.price = event.tokens_sold / event.eth_bought
            self.amount = event.tokens_sold
        else:
            raise ValueError()

    def __eq__(self, other):
        assert (isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
            self.timestamp == other.timestamp and \
            self.pair == other.pair and \
            self.is_sell == other.is_sell and \
            self.price == other.price and \
            self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))


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

        return Wad(self._contract.call().getEthToTokenInputPrice(amount.value))

    def get_token_eth_input_price(self, amount: Wad):
        assert(isinstance(amount, Wad))

        return Wad(self._contract.call().getTokenToEthInputPrice(amount.value))

    def get_eth_token_output_price(self, amount: Wad):
        assert(isinstance(amount, Wad))

        return Wad(self._contract.call().getEthToTokenOutputPrice(amount.value))

    def get_token_eth_output_price(self, amount: Wad):
        assert(isinstance(amount, Wad))

        return Wad(self._contract.call().getTokenToEthOutputPrice(amount.value))

    def get_current_liquidity(self):
        return Wad(self._contract.call().balanceOf(self.account_address.address))

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

    def get_all_trades(self, number_of_past_blocks: int) -> List[Trade]:
        assert isinstance(number_of_past_blocks, int)

        block_number = self._contract.web3.eth.blockNumber
        filter_params = {
            'address': self.exchange.address,
            'fromBlock': max(block_number-number_of_past_blocks, 0),
            'toBlock': block_number
        }

        logs = self.web3.eth.getLogs(filter_params)
        purchases = list(map(lambda l: PurchaseEvent.from_event(l, Uniswap.abi, self.web3), logs))
        purchases = filter(None, purchases)
        return list(map(lambda l: Trade(l, self.token.symbol()), purchases))

    def _deadline(self):
        """Get a predefined deadline."""
        return int(time.time()) + 1000
