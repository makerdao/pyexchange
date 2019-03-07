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
print("OKEXApi created\n")

#pair = "eth_usdt"
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


# response = okex.place_order(pair, False,
#                             Wad.from_number(0.00222),
#                             Wad.from_number(0.0153))
# print(response)
#2435596605531136 was never found
#print(okex.cancel_order(pair, "2437343317788672"))
#2437343317788672 buy  0.0153000 at 0.0022200000 on 2019-03-07 07:48:28

def print_orders(orders):
    for order in orders:
        side = "sell" if order.is_sell else "buy "
        print(f"{order.order_id} {side} {str(order.amount)[:9]} "
              f"at {str(order.price)[:12]} "
              f"on {datetime.datetime.utcfromtimestamp(order.timestamp)}")


# Gets open orders
#_orders = okex.get_orders(pair, 222)
# Gets all orders
_orders = okex.get_orders_history(pair, 9)
print_orders(_orders)

#trades = okex.get_all_trades(pair)[:-22]
#for order in trades:
#    side = "sell" if order.is_sell else "buy "
#    print(f"{side} {str(order.amount)[:9]} {order.amount_symbol} "
#          f"at {str(order.price)[:12]} "
#          f"on {datetime.datetime.utcfromtimestamp(order.timestamp)}")


