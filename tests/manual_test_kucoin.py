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

from pyexchange.kucoin import KucoinApi
from pymaker import Wad

kucoin = KucoinApi('https://openapi-v2.kucoin.com', sys.argv[1], sys.argv[2], sys.argv[3], 9.5)

# print("USER INFO")
# print(kucoinNew.get_user_info())
# print("Markwets INFO")
# print(kucoinNew.get_markets())
# print("BALANCES")
# print(kucoin.get_balances())
# print("DAI balance")
# print(kucoin.get_balance("DAI"))
# print("ETH balance")
# print(kucoin.get_balance("ETH"))
# print("ETH-DAI ticker")
# print(kucoin.ticker("ETH-DAI"))
# print("ETH-DAI order book")
# print(kucoin.order_book("USDT-DAI"))
# print("get markets")
# # print(kucoin.get_markets())
# print("place order")
# print(kucoin.place_order("USDT-DAI", True, Wad.from_number(80.222222222), Wad.from_number(0.12222223545)))
# print("place order")
# print(kucoin.place_order("ETH-DAI", False, Wad.from_number(20.1), Wad.from_number(0.1)))
# print(kucoin.place_order("ETH-DAI", True, Wad.from_number(220.1), Wad.from_number(0.1)))
# print("get coin balance")
# print(kucoin.get_fiat_balance("USD"))
# print("get all trades")
# print(kucoin.get_all_trades("ETH-DAI"))
# print("cancel order")
# print(kucoin.cancel_all_orders(False, "ETH-DAI"))
# print("get coin info")
# print(kucoin.get_coin_info("MKR"))
# print(kucoin.get_balance("MKR"))
# print(kucoin.get_trades("BTC-USDT"))
# print("get orders")
# print(kucoin.get_orders("ETH-DAI"))
# order = kucoin.place_order("ETH-DAI", True, Wad.from_number(135.1), Wad.from_number(0.1))

# def get_balance(token: str, type: str, balances):
#     try:
#         token_balance = next(filter(lambda balance: balance['currency'] == "DAI" and balance['type'] == type, balances))
#         return Wad.from_number(token_balance['balance'])
#     except:
#         return Wad.from_number(0)
#
# print(kucoin.get_balances())
# balances = kucoin.get_balances()
# print(get_balance("DAI", "trade", balances))
# print("cancel order")
# print(kucoin.cancel_order("5c74ebe907bab5738a1cb98d", False, "ETH-DAI"))
# print(kucoin.get_trades("ETH-DAI"))
# print("cancel order")
# print(kucoin.cancel_order("5c136626335e7e7346c12f82", False, "ETH-DAI"))
# print("get orders")
# print(kucoin.get_orders("ETH-DAI"))

