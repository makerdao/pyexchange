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
from pyflex import Address, Wad, Transact
from pyflex.model import Token
from pyflex.keys import register_private_key, register_key
from pyexchange.uniswapv2 import UniswapV2

USDC_KOVAN_ADDRESS = Address("0x198419c5c340e8de47ce4c0e4711a03664d42cb2")
USDC_MAINNET_ADDRESS = Address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
WBTC_KOVAN_ADDRESS = Address("0xe0c9275e44ea80ef17579d33c55136b7da269aeb")
ETH_ADDRESS = Address("0x0000000000000000000000000000000000000000")
WETH_ADDRESS = Address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
WETH_KOVAN_ADDRESS = Address("0xd0a1e359811322d97991e03f863a0c30c2cf029c")
DAI_ADDRESS = Address("0x6B175474E89094C44Da98b954EedeAC495271d0F")
DAI_KOVAN_ADDRESS = Address("0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa")
USDC_ADDRESS = Address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
MKR_ADDRESS = Address("0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2")
MKR_KOVAN_ADDRESS = Address("0xAaF64BFCC32d0F15873a02163e7E500671a4ffcD")
FACTORY_ADDRESS = Address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")
ROUTER_ADDRESS = Address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")

web3 = Web3(HTTPProvider(sys.argv[1], request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[2]
register_key(web3, sys.argv[3])

Transact.gas_estimate_for_bad_txs = 210000

dai = Token("DAI", DAI_KOVAN_ADDRESS, 18)
weth_kovan = Token("WETH", WETH_KOVAN_ADDRESS, 18)
weth_mainnet = Token("WETH", WETH_ADDRESS, 18)
usdc_kovan = Token("USDC", USDC_KOVAN_ADDRESS, 6)
usdc_mainnet = Token("USDC", USDC_MAINNET_ADDRESS, 6)

wbtc = Token('WBTC', Address("0xe0c9275e44ea80ef17579d33c55136b7da269aeb"), 8)
uniswap = UniswapV2(web3, dai, weth_kovan)

dai_weth_pair = Token("POOL", uniswap.get_pair_address(DAI_KOVAN_ADDRESS, WETH_KOVAN_ADDRESS), 18)
# uniswap.approve(wbtc, web3.toWei(5, 'ether'))
# uniswap.approve(weth, web3.toWei(5, 'ether'))



# amounts_in = uniswap.get_amounts_in(web3.toWei(0.5, 'ether'), [DAI_KOVAN_ADDRESS.address, MKR_KOVAN_ADDRESS.address])
# print(amounts_in)

# amounts_out = uniswap.get_amounts_out(web3.toWei(0.5, 'ether'), [DAI_KOVAN_ADDRESS.address, MKR_KOVAN_ADDRESS.address])
# print(amounts_out)

# eth_token_amounts_out = uniswap.get_amounts_out(Wad.from_number(0.5), [WETH_KOVAN_ADDRESS.address, DAI_KOVAN_ADDRESS.address])
# eth_token_amounts_out = uniswap.get_amounts_out(Wad.from_number(0.5), [DAI_KOVAN_ADDRESS.address, WETH_KOVAN_ADDRESS.address])


"""
    INITALIZATION
"""

dai_weth_kovan_pair_address = uniswap.get_pair_address(DAI_KOVAN_ADDRESS, WETH_KOVAN_ADDRESS)
print(dai_weth_kovan_pair_address)

dai_weth_kovan_exchange_rate = uniswap.get_exchange_rate()
print("exchange rate: ", dai_weth_kovan_exchange_rate)

dai_weth_kovan_current_liquidity = uniswap.get_current_liquidity()
print(dai_weth_kovan_current_liquidity)

permit = uniswap.permit()
print(permit)




"""
    ADD LIQUIDITY
"""
time.sleep(10)

add_token_pair_amounts = {
    "amount_a_desired": Wad.from_number(10),
    "amount_b_desired": Wad.from_number(10.1),
    "amount_a_min": Wad.from_number(9.95),
    "amount_b_min": Wad.from_number(10)
}
transaction = uniswap.add_liquidity(add_token_pair_amounts, dai, usdc_kovan)
res = transaction.transact()
print(res.successful)
print(res.transaction_hash.hex())

add_eth_pair_amounts = {
    "amount_a_desired": Wad.from_number(.1),
    "amount_b_desired": Wad.from_number(3.5),
    "amount_b_min": Wad.from_number(3),
    "amount_a_min": Wad.from_number(0.01)
}

# time.sleep(20)
# transaction = uniswap.add_liquidity_eth(add_eth_pair_amounts, dai)
# res = transaction.transact()
# print(res.successful)
# print(res.transaction_hash.hex())




"""
    REMOVE LIQUIDITY
"""

remove_token_amounts = {
    "liquidity": Wad.from_number(0.4294),
    "amountAMin": Wad.from_number(0),
    "amountBMin": Wad.from_number(0)
}
time.sleep(20)
# transaction = uniswap.remove_liquidity(DAI_KOVAN_ADDRESS, MKR_KOVAN_ADDRESS, remove_token_amounts)
transaction = uniswap.remove_liquidity_with_permit(remove_token_amounts, dai, usdc_kovan)
res = transaction.transact(from_address=Address(web3.eth.defaultAccount))
print(res)
print(res.transaction_hash.hex())

remove_eth_amounts = {
    "liquidity": Wad.from_number(0.00784088),
    "amountTokenMin": Wad.from_number(0),
    "amountETHMin": Wad.from_number(0)
}
# time.sleep(20)
# transaction = uniswap.remove_liquidity_eth(DAI_KOVAN_ADDRESS, remove_eth_amounts)
# res = transaction.transact(from_address=Address(web3.eth.defaultAccount))
# print(res)
# print(res.transaction_hash.hex())

# current_liq = uniswap.get_current_liquidity()
# print(current_liq)




"""
    SWAPS
"""

# transaction = uniswap.swap_exact_tokens_for_tokens(web3.toWei(2, 'ether'), web3.toWei(.097, 'ether'), [DAI_KOVAN_ADDRESS.address, MKR_KOVAN_ADDRESS.address])
# res = transaction.transact()
# print(res.successful)
# print(res.transaction_hash.hex())
