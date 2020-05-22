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
import dateutil.parser

from decimal import Decimal
from pprint import pformat
from typing import List, Optional
from eth_utils import from_wei
from web3.types import TxReceipt
from web3._utils.threads import Timeout

from dydx.client import Client
import dydx.constants as consts
import dydx.util as utils

from pyexchange.api import PyexAPI
from pyexchange.model import Order, Trade
from pymaker import Wad


class DydxOrder(Order):

    @staticmethod
    def from_message(item: list, pair: str, market_info: dict) -> Order:
        decimal_exponent = 18 - int(market_info['quoteCurrency']['decimals'])
        price = Wad.from_number(float(item['price']) * 10 ** decimal_exponent)

        return Order(order_id=item['id'],
                     timestamp=int(dateutil.parser.parse(item['createdAt']).timestamp()),
                     pair=pair,
                     is_sell=True if item['side'] == 'SELL' else False,
                     price=price,
                     amount=Wad.from_number(from_wei(abs(int(float(item['baseAmount']))), 'ether')))


class DydxTrade(Trade):

    @staticmethod
    def from_message(trade, pair: str, market_info: dict) -> Trade:
        decimal_exponent = 18 - int(market_info['quoteCurrency']['decimals'])
        price = Wad.from_number(float(trade['price']) * 10 ** decimal_exponent)

        return Trade(trade_id=trade['uuid'],
                     timestamp=int(dateutil.parser.parse(trade['createdAt']).timestamp()),
                     pair=trade["market"],
                     is_sell=True if trade['side'] == 'SELL' else False,
                     price=price,
                     amount=Wad.from_number(from_wei(abs(int(float(trade['amount']))), 'ether')))


class DydxApi(PyexAPI):
    """Dydx API interface.

        Documentation available here: https://docs.dydx.exchange/#/

        Startup guide here: https://medium.com/dydxderivatives/programatic-trading-on-dydx-4c74b8e86d88
    """

    logger = logging.getLogger()

    def __init__(self, node: str, private_key: str):
        assert (isinstance(node, str))
        assert (isinstance(private_key, str))

        self.client = Client(private_key=private_key, node=node)

        self.market_info = self.get_markets()

    def get_markets(self):
        return self.client.get_markets()['markets']

    def get_pair(self, pair: str):
        assert (isinstance(pair, str))
        return self.get_markets()[pair]

    # DyDx primarily uses Wei for units and needs to be converted to Wad
    def _convert_balance_to_wad(self, balance: dict, decimals: int) -> dict:
        wei_balance = float(balance['wei'])
        pending_balance = float(balance['pendingWei'])

        ## DyDx can have negative balances from native margin trading
        is_negative = False
        if wei_balance < 0:
            is_negative = True

        converted_balance = from_wei(abs(int(wei_balance)), 'ether')
        converted_pending_balance = from_wei(abs(int(pending_balance)), 'ether')

        if decimals == 6:
            converted_balance = from_wei(abs(int(wei_balance)), 'mwei')
            converted_pending_balance = from_wei(abs(int(pending_balance)), 'mwei')

        # reconvert Wad to negative value if balance is negative
        if is_negative == True:
            converted_balance = converted_balance * -1

        # Handle the edge case where orders are filled but balance change is still pending
        if converted_balance > 0:
            balance['wad'] = Wad.from_number(converted_balance) - Wad.from_number(converted_pending_balance)
        else:
            balance['wad'] = Wad.from_number(converted_balance) + Wad.from_number(converted_pending_balance)

        return balance

    # format balances response into a shape expected by keepers 
    def _balances_to_list(self, balances: dict) -> List:
        balance_list = []

        for i, (market_id, balance) in enumerate(balances.items()):
            decimals = 18
            if int(market_id) == consts.MARKET_ETH:
                balance['currency'] = 'ETH'
            elif int(market_id) == consts.MARKET_SAI:
                balance['currency'] = 'SAI'
            elif int(market_id) == consts.MARKET_USDC:
                balance['currency'] = 'USDC'
                decimals = 6
            elif int(market_id) == consts.MARKET_DAI:
                balance['currency'] = 'DAI'

            balance_list.append(self._convert_balance_to_wad(balance, decimals))

        return balance_list

    def get_balances(self):
        return self._balances_to_list(self.client.get_my_balances()['balances'])

    def get_orders(self, pair: str) -> List[Order]:
        assert (isinstance(pair, str))

        orders = self.client.get_my_orders(market=[pair], limit=None, startingBefore=None)
        open_orders = filter(lambda order: order['status'] == 'OPEN', orders['orders'])

        market_info = self.market_info[pair]

        return list(map(lambda item: DydxOrder.from_message(item, pair, market_info), open_orders))

    # Only sets allowances for solo market
    def set_allowances(self) -> bool:
        # Market IDs 0 (ETH), 2(USDC), 3(DAI) are traded
        allow_market_ids = [0, 2, 3]

        for market_id in allow_market_ids:
            try:
                allowance_tx_hash = self.client.eth.solo.set_allowance(
                    market=market_id)  # must only be called once, ever
                receipt = self.client.eth.get_receipt(allowance_tx_hash)
            except (Timeout, TypeError):
                logging.error(f"Unable to set allowance for market_id: {market_id}")
                continue

        return True

    def _get_market_id(self, token) -> int:
        assert (isinstance(token, str))

        if token.upper() == 'DAI':
            market_id = consts.MARKET_DAI
        elif token.upper() == 'USDC':
            market_id = consts.MARKET_USDC
        elif token.upper() == 'ETH' or token.upper() == 'WETH':
            market_id = consts.MARKET_ETH
        elif token.upper() == 'PBTC':
            market_id = consts.MARKET_PBTC

        return market_id

    # deposit_funds requires set_allowances() to be called once per token,
    # prior to any deposit attempt.
    def deposit_funds(self, token: str, amount: float) -> TxReceipt:
        assert (isinstance(token, str))
        assert (isinstance(amount, float))

        market_id = self._get_market_id(token)

        try:
            deposit_tx_hash = self.client.eth.solo.deposit(
                market=market_id,
                wei=utils.token_to_wei(amount, market_id)
            )
            receipt = self.client.eth.get_receipt(deposit_tx_hash)

            logging.info(f"Deposited {amount} of {token} into DYDX")
            return receipt
        except(Timeout, TypeError):
            raise RuntimeError('Unable to deposit funds. Try calling set_allowances() prior to deposit.')

    def withdraw_funds(self, token: str, amount: float) -> TxReceipt:
        assert (isinstance(token, str))
        assert (isinstance(amount, float))

        market_id = self._get_market_id(token)

        tx_hash = self.client.eth.solo.withdraw(
            market=market_id,
            wei=utils.token_to_wei(amount, market_id)
        )
        receipt = self.client.eth.get_receipt(tx_hash)

        logging.info(f"Withdrew {amount} of {token} from DYDX")

        return receipt

    def withdraw_all_funds(self, token: str) -> TxReceipt:
        assert (isinstance(token, str))

        market_id = self._get_market_id(token)

        # withdraws all available amount of the token including interest
        tx_hash = self.client.eth.solo.withdraw_to_zero(market=market_id)
        receipt = self.client.eth.get_receipt(tx_hash)

        logging.info(f"Withdrew all {token} from DYDX")

        return receipt

    def place_order(self, pair: str, is_sell: bool, price: float, amount: float) -> str:
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, float))
        assert (isinstance(amount, float))

        side = 'SELL' if is_sell else 'BUY'

        self.logger.info(f"Placing order ({side}, amount {amount} of {pair},"
                         f" price {price})...")

        tick_size = abs(Decimal(self.market_info[pair]['minimumTickSize']).as_tuple().exponent)
        # As market_id is used for amount, use baseCurrency instead of quoteCurrency
        market_id = self.market_info[pair]['baseCurrency']['soloMarketId']
        # Convert tokens with different decimals to standard wei units
        decimal_exponent = (18 - int(self.market_info[pair]['quoteCurrency']['decimals'])) * -1

        unformatted_price = price
        unformatted_amount = amount
        price = round(Decimal(unformatted_price * (10 ** decimal_exponent)), tick_size)
        amount = utils.token_to_wei(amount, market_id)

        created_order = self.client.place_order(
            market=pair,  # structured as <MAJOR>-<Minor>
            side=side,
            price=price,
            amount=amount,
            fillOrKill=False,
            postOnly=False
        )['order']
        order_id = created_order['id']

        self.logger.info(
            f"Placed {side} order #{order_id} with amount {unformatted_amount}, at price {unformatted_price}")
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

        market_info = self.market_info[pair]

        return list(map(lambda item: DydxTrade.from_message(item, pair, market_info), list(result['fills'])))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert (isinstance(pair, str))
        assert (page_number == 1)

        ## Specify which side of the order book to retrieve with pair
        # E.g WETH-DAI will not retrieve DAI-WETH
        result = self.client.get_fills(market=[pair], limit=100)['fills']
        trades = filter(lambda item: item['status'] == 'CONFIRMED', result)

        market_info = self.market_info[pair]

        return list(map(lambda item: DydxTrade.from_message(item, pair, market_info), trades))
