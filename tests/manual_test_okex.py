# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2019 reverendus and EdNoepel
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

import datetime
import sys

from pymaker import Wad
from pyexchange.okex import OKEXApi


okex = OKEXApi(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], 15.5)
print(sys.argv)
print("OKEXApi created\n")


pair = "mkr_usdt"
#l1 = okex.ticker(pair)
#print(f"best bid: {l1['best_bid']}  best ask: {l1['best_ask']}")
#book = okex.depth(pair)
#print(f"bids: {book['bids'][0:3]}")
#print(f"asks: {book['asks'][0:3]}")
# print(okex.candles(pair, '1min')[0:3])
# print()

balances = okex.get_balances()
print(f"BTC: {balances['BTC']}")
print(f"USDT: {balances['USDT']}")
print(f"ETH: {balances['ETH']}")
print(f"MKR: {balances['MKR']}")
# print()

# {
#     "base_currency": "MKR",
#     "base_increment": "0.000001",
#     "base_min_size": "0.001",
#     "instrument_id": "MKR-BTC",
#     "min_size": "0.001",
#     "product_id": "MKR-BTC",
#     "quote_currency": "BTC",
#     "quote_increment": "0.00000001",
#     "size_increment": "0.000001",
#     "tick_size": "0.00000001"
# },

# price in terms of quote currency (USDT), size in terms of base currency (MKR)
# response = okex.place_order(pair, False, Wad.from_number(691.6), Wad.from_number(0.25))
# print(response)
print(okex.cancel_order(pair, "2502374107516928"))


def print_orders(orders):
    print(f"received {len(orders)} orders")
    for index, order in enumerate(orders):
        side = "sell" if order.is_sell else "buy "
        fill_status = f"with {order.filled_amount} filled" if order.filled_amount > Wad(0) else "unfilled"
        print(f"[{index}] {order.order_id} {order.status:<12} {side} {str(order.amount)[:9]} "
              f"at {str(order.price)[:12]} "
              f"on {datetime.datetime.utcfromtimestamp(order.timestamp)} "
              + fill_status)
        #f"page {order.page}")

def print_trades(trades):
    for trade in trades:
        side = "sell" if trade.is_sell else "buy "
        print(f"{side} {str(trade.amount)[:9]} {trade.amount_symbol} "
              f"at {str(trade.price)[:12]} "
              f"{pair.split('_')[1]} "
              f"on {datetime.datetime.utcfromtimestamp(trade.timestamp)}")
        

# Gets open orders
#orders = okex.get_orders(pair)
#print_orders(orders)
# Gets all orders
#orders = okex.get_orders_history(pair, 9, "all")
#print_orders(orders)

# trades = okex.get_trades(pair)
#trades = okex.get_all_trades(pair)
# print_trades(trades[:9])

