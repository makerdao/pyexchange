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
from pymaker.keys import register_key_file, register_private_key
from pymaker.zrxv2 import ZrxExchangeV2, Asset
from pymaker.token import ERC20Token

# Infura and own wallet settings
logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)
WEB3_INFURA_API_KEY = "infura project id here"
INFURA_URL = "https://mainnet.infura.io/v3/" + WEB3_INFURA_API_KEY
WALLET_ADDRESS = "eth wallet address here"
WALLET_PRIVATE_KEY = "pkey of eth wallet address here"

# setting Infura provider and import external pkey
infura_provider = HTTPProvider(INFURA_URL)
web3 = Web3(infura_provider)
register_private_key(web3, WALLET_PRIVATE_KEY)
web3.eth.defaultAccount = WALLET_ADDRESS
EXCHANGE_ADDRESS = Address("0x4f833a24e1f95d70f028921e27040ca56e09ab0b")

zrx_v2_exchange = ZrxExchangeV2(web3=web3, address=EXCHANGE_ADDRESS)
ethfinex_trustless_api = TEthfinexApi(zrx_v2_exchange, 'https://api.ethfinex.com', 15.5)

ethfinex_symbol = ethfinex_trustless_api.get_symbols()
ethfinex_symbols_details = ethfinex_trustless_api.get_symbols_details()
ethfinex_config = ethfinex_trustless_api.get_config()['0x']

ETHFINEX_ADDRESS = Address(ethfinex_config['ethfinexAddress'])
#EXCHANGE_ADDRESS = Address(ethfinex_config['exchangeAddress'])

DAI_WRAPPER_ADDRESS = Address(ethfinex_config['tokenRegistry']['DAI']['wrapperAddress'])
DAI_TOKEN_ADDRESS = Address(ethfinex_config['tokenRegistry']['DAI']['tokenAddress'])

ETH_WRAPPER_ADDRESS = Address(ethfinex_config['tokenRegistry']['ETH']['wrapperAddress'])

MKR_WRAPPER_ADDRESS = Address(ethfinex_config['tokenRegistry']['MKR']['wrapperAddress'])
MKR_TOKEN_ADDRESS = Address(ethfinex_config['tokenRegistry']['MKR']['tokenAddress'])

OMG_WRAPPER_ADDRESS = Address(ethfinex_config['tokenRegistry']['OMG']['wrapperAddress'])


# DAI
dai_token = ERC20Token(web3, DAI_TOKEN_ADDRESS)
# you have to approve each token if it is its first time use
dai_approve = dai_token.approve(DAI_WRAPPER_ADDRESS)
print(dai_approve.transact())
dai_wrapper = TEthfinexToken(web3, DAI_WRAPPER_ADDRESS, "DAI")
# lock token amount on wrapper
dai_transact = dai_wrapper.deposit(Wad.from_number(0.40), 1)
print(dai_transact.transact())
print(dai_wrapper.balance_of(Address(web3.eth.defaultAccount)))


# MKR
mkr_token = ERC20Token(web3, MKR_TOKEN_ADDRESS)
mkr_approve = mkr_token.approve(MKR_WRAPPER_ADDRESS)
print(mkr_approve.transact())
mkr_wrapper = TEthfinexToken(web3, MKR_WRAPPER_ADDRESS, "MKR")
# lock token
mkr_transact = mkr_wrapper.deposit(Wad.from_number(0.001), 1)
print(mkr_transact.transact())
print(mkr_wrapper.balance_of(Address(web3.eth.defaultAccount)))


# ETH
# eth does not need to approve
eth_wrapper = TEthfinexToken(web3, ETH_WRAPPER_ADDRESS, "ETH")
# lock token
eth_transact = eth_wrapper.deposit(Wad.from_number(0.11))
print(eth_transact.transact())
print(eth_wrapper.balance_of(Address(web3.eth.defaultAccount)))


# buy order - buy OMG (16) with ETH (0.12) (fee from OMG)
placed_order_buy = ethfinex_trustless_api.place_order(False,
                                        OMG_WRAPPER_ADDRESS,
                                        Wad.from_number(16),
                                        ETH_WRAPPER_ADDRESS,
                                        Wad.from_number(0.12),
                                        ETHFINEX_ADDRESS,
                                        "OMGETH")
print(f"Placed order {placed_order_buy}")
print(ethfinex_trustless_api.cancel_order(placed_order_buy))


# sell order - sell omg (12) for eth (0.11) (fee from ETH)
placed_order_sell = ethfinex_trustless_api.place_order(True,
                                        OMG_WRAPPER_ADDRESS,
                                        Wad.from_number(12),
                                        ETH_WRAPPER_ADDRESS,
                                        Wad.from_number(0.11),
                                        ETHFINEX_ADDRESS,
                                        "OMGETH")
print(f"Placed order {placed_order_sell}")
print(ethfinex_trustless_api.cancel_order(placed_order_sell))
print(ethfinex_trustless_api.get_trades("OMGETH"))
