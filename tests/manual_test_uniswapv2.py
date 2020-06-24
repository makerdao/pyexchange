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

from web3 import Web3, HTTPProvider
from pymaker import Address, Wad, Transact
from pymaker.model import Token
from pymaker.keys import register_private_key, register_key
from pyexchange.uniswapv2 import UniswapV2

WETH_ADDRESS = Address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
WETH_KOVAN_ADDRESS = Address("0xd0a1e359811322d97991e03f863a0c30c2cf029c")
DAI_ADDRESS = Address("0x6B175474E89094C44Da98b954EedeAC495271d0F")
DAI_KOVAN_ADDRESS = Address("0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa")
USDC_ADDRESS = Address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
MKR_ADDRESS = Address("0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2")
MKR_KOVAN_ADDRESS = Address("0xAaF64BFCC32d0F15873a02163e7E500671a4ffcD")
FACTORY_ADDRESS = Address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")
ROUTER_ADDRESS = Address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")

web3 = Web3(HTTPProvider(sys.argv[1], request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[2]
register_key(web3, sys.argv[3])

Transact.gas_estimate_for_bad_txs = 23000

uniswap = UniswapV2(web3, 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2', ROUTER_ADDRESS, FACTORY_ADDRESS)
# current_liq = uniswap.get_current_liquidity()
# print(current_liq)
# dai = Token("DAI", DAI_KOVAN_ADDRESS, 18)
print(uniswap.get_pair_address(DAI_KOVAN_ADDRESS.address, WETH_KOVAN_ADDRESS.address))
# print(uniswap.get_pair_address(DAI_KOVAN_ADDRESS.address, WETH_ADDRESS.address))
dai_weth_pair = Token("POOL", uniswap.get_pair_address(DAI_KOVAN_ADDRESS.address, WETH_KOVAN_ADDRESS.address), 18)
uniswap.approve(dai_weth_pair, web3.toWei(5, 'ether'))

add_token_pair_amounts = {
    "amount_a_desired": web3.toWei(1.9, 'ether'),
    "amount_b_desired": web3.toWei(.1, 'ether'),
    "amount_a_min": web3.toWei(1.8, 'ether'),
    "amount_b_min": web3.toWei(.095, 'ether')
}
# time.sleep(20)
# transaction = uniswap.add_liquidity(add_token_pair_amounts, DAI_KOVAN_ADDRESS, MKR_KOVAN_ADDRESS)
# res = transaction.transact()
# print(res.successful)
# print(res.transaction_hash.hex())

add_eth_pair_amounts = {
    "amount_token_desired": web3.toWei(2.4, 'ether'),
    "amount_token_min": web3.toWei(2.1, 'ether'),
    "amount_eth_min": web3.toWei(.015, 'ether')
}
# time.sleep(20)
# transaction = uniswap.add_liquidity_eth(add_eth_pair_amounts, DAI_ADDRESS)
# transaction = uniswap.add_liquidity_eth(add_eth_pair_amounts, DAI_KOVAN_ADDRESS)
# res = transaction.transact()
# print(res)
# print(res.transaction_hash.hex())

# balances = uniswap.get_balances()
# print(balances)

# remove_token_amounts = {
#     "liquidity": web3.toWei(0.4294, 'ether'),
#     "amountAMin": web3.toWei(1.89999, 'ether'),
#     "amountBMin": web3.toWei(.0971676, 'ether')
# }
remove_token_amounts = {
    "liquidity": web3.toWei(0.4294, 'ether'),
    "amountAMin": web3.toWei(0, 'ether'),
    "amountBMin": web3.toWei(0, 'ether')
}
# time.sleep(20)
# transaction = uniswap.remove_liquidity(DAI_KOVAN_ADDRESS, MKR_KOVAN_ADDRESS, remove_token_amounts)
# res = transaction.transact(from_address=Address(web3.eth.defaultAccount))
# print(res)
# print(res.transaction_hash.hex())

remove_eth_amounts = {
    "liquidity": web3.toWei(0.00784088, 'ether'),
    "amountTokenMin": web3.toWei(0, 'ether'),
    "amountETHMin": web3.toWei(0, 'ether')
}
# remove_eth_amounts = {
#     "liquidity": web3.toWei(0, 'ether'),
#     "amountTokenMin": web3.toWei(0, 'ether'),
#     "amountETHMin": web3.toWei(0, 'ether')
# }
time.sleep(20)
transaction = uniswap.remove_liquidity_eth(DAI_KOVAN_ADDRESS, remove_eth_amounts)
res = transaction.transact(from_address=Address(web3.eth.defaultAccount))
print(res)
print(res.transaction_hash.hex())

# transaction = uniswap.swap_exact_tokens_for_tokens(web3.toWei(2, 'ether'), web3.toWei(.097, 'ether'), [DAI_KOVAN_ADDRESS.address, MKR_KOVAN_ADDRESS.address])
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
