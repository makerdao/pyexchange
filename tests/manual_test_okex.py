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

import sys

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
print(f"ETH: {balances['ETH']}")
print(f"MKR: {balances['MKR']}")
print(f"USDC: {balances['USDC']}")
print(f"USDT: {balances['USDT']}")
print()

#print(okex.get_orders('eth_usdt', 1000))
#print(okex.get_orders(number_of_orders=1022))
#print(okex.get_orders_history('mkr_eth', 369))

#print(okex.cancel_order("BTC-USDT", "2229535858593792"))