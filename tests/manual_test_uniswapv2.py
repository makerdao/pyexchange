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
import time

from pymaker import Address, Wad
from web3 import Web3, HTTPProvider
from pymaker.keys import register_private_key, register_key
from pyexchange.uniswapv2 import UniswapV2

WETH_ADDRESS = Address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
DAI_ADDRESS = Address("0x6B175474E89094C44Da98b954EedeAC495271d0F")
DAI_KOVAN_ADDRESS = Address("0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa")
USDC_ADDRESS = Address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
MKR_ADDRESS = Address("0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2")
FACTORY_ADDRESS = Address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")
ROUTER_ADDRESS = Address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")

web3 = Web3(HTTPProvider(sys.argv[1], request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[2]
register_key(web3, sys.argv[3])
# register_private_key(web3, sys.argv[3])

uniswap = UniswapV2(web3, 'https://api.thegraph.com/subgraphs/name/graphprotocol/uniswap', ROUTER_ADDRESS, FACTORY_ADDRESS)
# current_liq = uniswap.get_current_liquidity()
# print(current_liq)

# token_a_desired = 45
# token_b_desired = .2
# token_a_min = 20
# token_b_min = .1
token_a_desired = 45000000000000000000
token_b_desired = 200000000000000000
token_a_min = 2000000000000000000
token_b_min = 100000000000000000

token_pair_amounts = {
    "amount_a_desired": token_a_desired,
    "amount_b_desired": token_b_desired,
    "amount_a_min": token_a_min,
    "amount_b_min": token_b_min
}
# time.sleep(20)
# transaction = uniswap.add_liquidity(token_pair_amounts, DAI_ADDRESS, WETH_ADDRESS)
# res = transaction.transact()
# print(res.successful)
# print(res.transaction_hash.hex())

eth_pair_amounts = {
    "amount_token_desired": web3.toWei(2.4, 'ether'),
    "amount_token_min": web3.toWei(2.1, 'ether'),
    "amount_eth_min": web3.toWei(.015, 'ether')
}
# time.sleep(20)
# transaction = uniswap.add_liquidity_eth(eth_pair_amounts, DAI_ADDRESS)
# transaction = uniswap.add_liquidity_eth(eth_pair_amounts, DAI_KOVAN_ADDRESS)
# res = transaction.transact()
# print(res)
# print(res.transaction_hash.hex())

remove_eth_liquidity_amounts = {
    "liquidity": web3.toWei(.00784088, 'ether'),
    "amountTokenMin": web3.toWei(.124079, 'ether'),
    "amountETHMin": web3.toWei(.000512379, 'ether')
}

# time.sleep(20)
transaction = uniswap.remove_liquidity_eth(DAI_KOVAN_ADDRESS, remove_eth_liquidity_amounts)
res = transaction.transact(from_address=Address(web3.eth.defaultAccount))
print(res)
print(res.transaction_hash.hex())
# [{'from': '0x332f60EDC783E4Db3E0a18F8dFEB368Ae178CCd9', 'to': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D', 'data': '0xaf2979eb0000000000000000000000006b175474e89094c44da98b954eedeac495271d0f000000000000000000000000000000000000000000000000001bdb3d2320600000000000000000000000000000000000000000000000000001b85a0c9e9ec0000000000000000000000000000000000000000000000000000001d2762e366000000000000000000000000000332f60edc783e4db3e0a18f8dfeb368ae178ccd9000000000000000000000000000000000000000000000000000000005ef14c5d'}]
# transaction = uniswap.swap_exact_eth_for_tokens(2300000000000000000, 100000000000000000, [WETH_ADDRESS.address, DAI_ADDRESS.address])
# res = transaction.transact()
# print(res.successful)
# print(res.transaction_hash.hex())

# transaction = uniswap.swap_exact_tokens_for_tokens(21, 20, [DAI_ADDRESS.address, USDC_ADDRESS.address])
# res = transaction.transact()
# print(res.successful)
# print(res.transaction_hash.hex())

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

# print(uniswap.get_block())
