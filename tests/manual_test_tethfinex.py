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

import logging
import sys
from web3 import Web3, HTTPProvider

from pyexchange.tethfinex import TEthfinexToken, TEthfinexApi
from pymaker import Address, Wad
from pymaker.keys import register_key_file
from pymaker.zrx import ZrxExchange


logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[1]

EXCHANGE_ADDRESS = Address("0xdcdb42c9a256690bd153a7b409751adfc8dd5851")
DAI_ADDRESS = Address("0xd9ebebfdab08c643c5f2837632de920c70a56247")
ETH_ADDRESS = Address("0xaa7427d8f17d87a28f5e1ba3adbb270badbe1011")
FEE_ADDRESS = Address("0x61b9898c9b60a159fc91ae8026563cd226b7a0c1")

dai_wrapper = TEthfinexToken(web3, DAI_ADDRESS, "DAI")
# print(dai_wrapper.balance_of(Address(web3.eth.defaultAccount)))
# print(dai_wrapper.deposit(Wad.from_number(15)).transact())
# print(dai_wrapper.balance_of(Address(web3.eth.defaultAccount)))


# ethfinex_trustless = TEthfinexToken(web3, EXCHANGE_ADDRESS)
zrx_exchange = ZrxExchange(web3=web3, address=EXCHANGE_ADDRESS)
ethfinex_trustless_api = TEthfinexApi(zrx_exchange, 'https://api.ethfinex.com', 15.5)
# print(ethfinex_trustless_api.get_symbols())
# print(ethfinex_trustless_api.get_config())

# placed_order = ethfinex_trustless_api.place_order(False,
#                                        DAI_ADDRESS,
#                                        Wad.from_number(86.4),
#                                        ETH_ADDRESS,
#                                        Wad.from_number(0.8),
#                                        FEE_ADDRESS,
#                                        "DAIETH")
# print(f"Placed order {placed_order}")
# print(ethfinex_trustless_api.get_orders("tDAIUSD"))
# print(ethfinex_trustless_api.cancel_order(placed_order))

# placed_order = ethfinex_trustless_api.place_order(True,
#                                        ETH_ADDRESS,
#                                        Wad.from_number(0.8),
#                                        DAI_ADDRESS,
#                                        Wad.from_number(84.8),
#                                        FEE_ADDRESS,
#                                        "DAIETH")
# print(f"Placed order {placed_order}")
# print(ethfinex_trustless_api.get_orders("tDAIUSD"))
# print(ethfinex_trustless_api.cancel_order(placed_order))
# ethfinex_trustless_api.get_all_trades("DAIETH")
print(ethfinex_trustless_api.get_trades("tDAIUSD"))


eth_wrapper = TEthfinexToken(web3, ETH_ADDRESS, "ETH")
# print(eth_wrapper.balance_of(Address(web3.eth.defaultAccount)))
# print(eth_wrapper.deposit(Wad.from_number(1)).transact())
# print(eth_wrapper.balance_of(Address(web3.eth.defaultAccount)))

# print(ethfinex_trustless_eth.deposit(Wad.from_number(0.9)).transact())
# print(ethfinex_trustless_eth.balance_of(Address(web3.eth.defaultAccount)))
# print(ethfinex_trustless_eth.balance_of(Address(web3.eth.defaultAccount)))
