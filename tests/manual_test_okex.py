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

import datetime
import sys

from pymaker import Wad
from pyexchange.okex import OKEXApi


okex = OKEXApi(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], 15.5)
print(sys.argv)
print("OKEXApi created\n")


pair = "mkr_btc"
l1 = okex.ticker(pair)
print(f"best bid: {l1['best_bid']}  best ask: {l1['best_ask']}")
# book = okex.depth(pair)
# print(f"bids: {book['bids'][0:3]}")
# print(f"asks: {book['asks'][0:3]}")
# print(okex.candles(pair, '1min')[0:3])
print()

balances = okex.get_balances()
#print(balances)
print(f"BTC: {balances['BTC']}")
print(f"ETH: {balances['ETH']}")
print(f"MKR: {balances['MKR']}")
#print(f"USDC: {balances['USDC']}")
#print(f"USDT: {balances['USDT']}")
print()

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

# price in terms of quote currency (BTC), size in terms of base currency (MKR)
# response = okex.place_order(pair, True, Wad.from_number(0.180), Wad.from_number(0.1))
# print(response)
#2435596605531136 was never found
#print(okex.cancel_order(pair, "2437343317788672"))
#2437343317788672 buy  0.0153000 at 0.0022200000 on 2019-03-07 07:48:28
#2446198020705280

def print_orders(orders):
    print(f"received {len(orders)} orders")
    for index, order in enumerate(orders):
        side = "sell" if order.is_sell else "buy "
        print(f"[{index}] {order.order_id} {side} {str(order.amount)[:9]} "
              f"at {str(order.price)[:12]} "
              f"on {datetime.datetime.utcfromtimestamp(order.timestamp)} ")
              #f"page {order.page}")

def check_orders(orders):
    by_oid = {}
    duplicate_count = 0
    duplicate_first_found = -1
    missorted_found = False
    last_order_timestamp = 0
    for index, order in enumerate(orders):
        if order.order_id in by_oid:
            duplicate_count += 1
            if duplicate_first_found < 0:
                duplicate_first_found = index
        else:
            by_oid[order.order_id] = order
            if not missorted_found and last_order_timestamp > 0:
                if order.timestamp > last_order_timestamp:
                    print(f"missorted order found at index {index}")
                    missorted_found = True
            last_order_timestamp = order.timestamp
    if duplicate_count > 0:
        print(f"{duplicate_count} duplicate orders were found, "
              f"starting at index {duplicate_first_found}")
    else:
        print("no duplicates were found")

def print_trades(trades):
    for order in trades:
        side = "sell" if order.is_sell else "buy "
        print(f"{side} {str(order.amount)[:9]} {order.amount_symbol} "
              f"at {str(order.price)[:12]} "
              f"{pair.split('_')[1]} "
              f"on {datetime.datetime.utcfromtimestamp(order.timestamp)}")

# Gets open orders
# orders = okex.get_orders(pair)
# Gets all orders
# orders = okex.get_orders_history(pair, 22, 'filled')
# print_orders(orders)
# check_orders(orders)

#trades = okex.get_trades(pair)
trades = okex.get_all_trades(pair)
print_trades(trades)

