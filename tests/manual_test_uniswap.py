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

import sys

from pymaker import Address, Wad
from web3 import Web3, HTTPProvider
from pymaker.keys import register_key
from pyexchange.uniswap import Uniswap

DAI_ADDRESS = Address("0x89d24A6b4CcB1B6fAA2625fE562bDD9a23260359")
MKR_ADDRESS = Address("0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2")
ETH_DAI_ADDRESS = Address("0x09cabEC1eAd1c0Ba254B09efb3EE13841712bE14")
MKR_DAI_ADDRESS = Address("0x2C4Bd064b998838076fa341A83d007FC2FA50957")
FACTORY_ADDRESS = Address("0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95")

web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[1]
register_key(web3, sys.argv[2])

uniswap = Uniswap(web3, DAI_ADDRESS, ETH_DAI_ADDRESS)
current_liq = uniswap.get_current_liquidity()
print(current_liq)

amount = Wad.from_number(0.2)
transaction = uniswap.add_liquidity(amount)
res = transaction.transact()
print(res.successful)
print(res.transaction_hash.hex())

current_liq = uniswap.get_current_liquidity()
print(current_liq)

transaction = uniswap.remove_liquidity(current_liq)
transact = transaction.transact()
print(transact.successful)
print(transact.transaction_hash.hex())

current_liq = uniswap.get_current_liquidity()
print(current_liq)


