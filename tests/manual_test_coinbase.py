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

import logging
import sys

from pyexchange.coinbase import CoinbaseApi
from pyflex import Address, Wad

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)

# ctor params: api_server: str, api_key: str, secret_key: str, password: str
coinbase = CoinbaseApi("https://api.pro.coinbase.com", sys.argv[1], sys.argv[2], sys.argv[3], 9.5)

# print("get balances")
# print(coinbase.get_balances())
print("get balance ETH")
print(coinbase.get_balance("ETH"))
# print("get balance BTC")
# print(coinbase.get_balance("BTC"))

order_id = coinbase.place_order("ETH-USDC", True, Wad.from_number(444), round(Wad.from_number(0.0156547676576), 8))
print(coinbase.get_orders("ETH-USDC"))
coinbase.cancel_order(order_id)
print(coinbase.get_orders("ETH-USDC"))

# order_id = coinbase.place_order("ETH-USDC", False, Wad.from_number(90), round(Wad.from_number(0.01), 8))
# print("place orders")
# order_id = coinbase.place_order("ETH-USDC", False, Wad.from_number(90.11111111111), Wad.from_number(0.0156547676576))
# print(coinbase.cancel_order(order_id))

# print(coinbase.get_trades("ETH-USDC"))
# print("place orders")
# order_id = coinbase.place_order("ETH-USDC", False, Wad.from_number(20.11111111111), Wad.from_number(0.0156547676576))
# print(order_id)

# print("cancel orders")
# print(coinbase.cancel_all_orders())

# print("get trades")
# print(coinbase.get_trades("ETH-USDC"))
# print("wallet address")
# print(coinbase.get_coinbase_wallet_address("ETH"))
# print("withdraw")
# print(coinbase.withdraw(Wad.from_number(0.0782), "ETH", Address('0x?')))

# pprint(coinbase.get_profiles())
# print(coinbase.get_profile("default"))
# print(coinbase.get_profile("Testing"))
# coinbase.transfer(Wad.from_number(0.1), "ETH", "default", "Testing")
