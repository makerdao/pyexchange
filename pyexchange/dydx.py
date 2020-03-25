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

import logging
from pprint import pformat

from dydx.client import Client
import dydx.constants as consts
import dydx.util as utils

from pyexchange.api import PyexAPI
from pymaker import Wad
from typing import List, Optional

import dateutil.parser

import dydx.constants as consts
import dydx.util as utils


class Order:
    def __init__(self,
                 order_id: str,
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert (isinstance(timestamp, int))
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, Wad))
        assert (isinstance(amount, Wad))

        self.order_id = order_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount * self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount * self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def to_order(item: list, pair: str):
        return Order(order_id=item['id'],
                     timestamp=int(dateutil.parser.parse(item['createdAt']).timestamp()),
                     pair=pair,
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['baseAmount']))


class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 pair: str,
                 price: Wad,
                 amount: Wad):
        assert (isinstance(trade_id, str) or (trade_id is None))
        assert (isinstance(timestamp, int))
        assert (isinstance(pair, str))
        assert (isinstance(price, Wad))
        assert (isinstance(amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.pair = pair
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert (isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.pair,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_list(trade):
        return Trade(trade_id=trade['uuid'],
                     timestamp=int(dateutil.parser.parse(trade['createdAt']).timestamp()),
                     pair=trade["market"],
                     price=Wad.from_number(trade['price']),
                     amount=Wad(int(trade['amount'])))


class DydxApi(PyexAPI):
    """Dydx API interface.

        Documentation available here: https://docs.dydx.exchange/#/

        Startup guide here: https://medium.com/dydxderivatives/programatic-trading-on-dydx-4c74b8e86d88
    """

    logger = logging.getLogger()

    def __init__(self, node: str, private_key: str):
        assert (isinstance(node, str))
        assert (isinstance(private_key, str))

        # self.address = web3.eth.accounts.privateKeyToAccount(privateKey)['address']
        self.client = Client(private_key=private_key, node=node)

    def get_markets(self):
        return self.client.get_pairs()['pairs']

    def get_pair(self, pair: str):
        assert (isinstance(pair, str))
        return next(filter(lambda symbol: symbol['name'] == pair, self.get_markets()))

    def _balances_to_list(self, balances) -> List:
        balance_list = []

        for token, balance in enumerate(balances):
            if token == 0:
                balances[str(token)]['currency'] = 'ETH'
            elif token == 1:
                balances[str(token)]['currency'] = 'SAI'
            elif token == 2:
                balances[str(token)]['currency'] = 'USDC'
            elif token == 3:
                balances[str(token)]['currency'] = 'DAI'

            balance_list.append(balances[str(token)])

        return balance_list

    def get_balances(self):
        return self._balances_to_list(self.client.get_my_balances()['balances'])

    def get_orders(self, pair: str) -> List[Order]:
        assert (isinstance(pair, str))

        orders = self.client.get_my_orders(market=[pair], limit=None, startingBefore=None)

        return list(map(lambda item: Order.to_order(item, pair), orders['orders']))

    def deposit_funds(self, token, amount: float):
        assert (isinstance(amount, float))

        market = consts.MARKET_ETH

        # determine if 6 or 18 decimals are needed for wei conversion
        if token == 'USDC':
            market = consts.MARKET_USDC
        else:
            market = consts.MARKET_ETH

        tx_hash = self.client.eth.deposit(
            market=market,
            wei=utils.token_to_wei(amount, market)
        )

        receipt = self.client.eth.get_receipt(tx_hash)
        return receipt

    def place_order(self, pair: str, is_sell: bool, price: float, amount: float) -> str:
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, float))
        assert (isinstance(amount, float))

        side = 'SELL' if is_sell else 'BUY'

        self.logger.info(f"Placing order ({side}, amount {amount} of {pair},"
                         f" price {price})...")

        ## Need to retrieve the market_id used by a given token as all trades in DyDx use Wei as standard unit.
        ## Currently orders, even involving usdc, utilize 18 decimals so can hardcode consts.MARKET_ETH

        # market_id = 0
        # if 'ETH' in pair:
        #     market_id = consts.MARKET_ETH
        # elif pair == 'DAI-USDC' and is_sell is True:
        #     market_id = consts.MARKET_USDC
        # elif pair == 'DAI-USDC' and is_sell is False:
        #     market_id = consts.MARKET_DAI

        created_order = self.client.place_order(
            market=pair,  # structured as <MAJOR>-<Minor>
            side=side,
            price=price,
            amount=utils.token_to_wei(amount, consts.MARKET_ETH),
            fillOrKill=False,
            postOnly=False
        )['order']

        order_id = created_order['id']

        self.logger.info(f"Placed order as #{order_id}")
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        assert (isinstance(order_id, str))

        self.logger.info(f"Cancelling order #{order_id}...")

        canceled_order = self.client.cancel_order(hash=order_id)
        return canceled_order['order']['id'] == order_id

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert (isinstance(pair, str))
        assert (isinstance(page_number, int))

        result = self.client.get_my_fills(market=[pair])
        return list(map(lambda item: Trade.from_list(item), list(result['fills'])))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert (isinstance(pair, str))
        assert (page_number == 1)

        result = self.client.get_fills(market=[pair], limit=10)['fills']
        trades = filter(lambda item: item['status'] == 'CONFIRMED' and item['order']['status'] == 'FILLED', result)

        return list(map(lambda item: Trade.from_list(item), trades))
