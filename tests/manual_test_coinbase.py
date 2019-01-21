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
import base64

from pyexchange.coinbase import CoinbaseApi
from pymaker import Wad

coinbase = CoinbaseApi("https://api.pro.coinbase.com", sys.argv[1], sys.argv[2], sys.argv[3], 9.5)

# print("get orders")
# print(coinbase.get_balances())
# # print("get balance ETH")
# print(coinbase.get_balance("USDC"))
# print("get balance ETH")
# print(coinbase.get_balance("BTC"))
# print("cancel orders")
# print(coinbase.cancel_all_orders())
# print("cancel orders")
# print(coinbase.cancel_order("144c6f8e-713f-4682-8435-5280fbe8b2b4"))
# print("place orders")
# order_id = coinbase.place_order("ETH-USDC", True, Wad.from_number(120), round(Wad.from_number(0.0156547676576), 8))
# print("cancel order")
# print(coinbase.cancel_order(order_id))
# order_id = coinbase.place_order("ETH-USDC", False, Wad.from_number(90), round(Wad.from_number(0.01), 8))
# print("place orders")
# order_id = coinbase.place_order("ETH-USDC", False, Wad.from_number(90.11111111111), Wad.from_number(0.0156547676576))
# print(coinbase.cancel_order(order_id))
print(coinbase.get_trades("ETH-USDC"))
# print("place orders")
# order_id = coinbase.place_order("ETH-USDC", False, Wad.from_number(20.11111111111), Wad.from_number(0.0156547676576))
# print(order_id)
# print("get orders")
# print(coinbase.get_orders("ETH-USDC"))
# print("cancel orders")
# print(coinbase.cancel_all_orders())
# print("get trades")
# print(coinbase.get_trades("ETH-USDC"))


