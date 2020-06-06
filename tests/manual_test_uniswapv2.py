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

import sys

from pymaker import Address, Wad
from web3 import Web3, HTTPProvider
from pymaker.keys import register_key
from pyexchange.uniswapv2 import UniswapV2

WETH_ADDRESS = Address("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
DAI_ADDRESS = Address("0x6b175474e89094c44da98b954eedeac495271d0f")
MKR_ADDRESS = Address("0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2")
FACTORY_ADDRESS = Address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")
ROUTER_ADDRESS = Address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")

web3 = Web3(HTTPProvider(sys.argv[1], request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[2]
register_key(web3, sys.argv[3])

uniswap = UniswapV2(web3, DAI_ADDRESS, ETH_DAI_ADDRESS)
# current_liq = uniswap.get_current_liquidity()
# print(current_liq)

token_a_desired = Wad.from_number(20.0)
token_b_desired = Wad.from_number(0.2)
token_a_min = Wad.from_number()
token_b_min = Wad.from_number()
amounts = {}

transaction = uniswap.add_liquidity(amounts, DAI_ADDRESS, WETH_ADDRESS)
res = transaction.transact()
print(res.successful)
print(res.transaction_hash.hex())

# current_liq = uniswap.get_current_liquidity()
# print(current_liq)
#
# transaction = uniswap.remove_liquidity(current_liq)
# transact = transaction.transact()
# print(transact.successful)
# print(transact.transaction_hash.hex())
#
# current_liq = uniswap.get_current_liquidity()
# print(current_liq)


