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
from web3 import Web3, HTTPProvider

from pyexchange.idex import IDEXApi, IDEX
from pymaker import Address, Wad


logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[1]
idex = IDEX(web3, Address('0x2a0c0dbecc7e4d658f48e01e3fa353f44050c208'))
idex_api = IDEXApi(idex, 'https://api.idex.market', 15.5)

# print(idex.balance_of(Address(web3.eth.defaultAccount)))
# idex.deposit(Wad.from_number(0.5)).transact()

print(idex.balance_of(Address(web3.eth.defaultAccount)))
print(idex.balance_of_token(Address('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'), Address(web3.eth.defaultAccount)))

# print(idex_api.next_nonce())
# print(idex_api.ticker('DAI_ETH'))
# print(idex_api.get_balances())
# print(idex_api.get_orders('DAI_ETH'))
print(idex_api.get_orders('DAI_ETH'))
exit(-1)

print(idex_api.place_order(pay_token=Address('0x0000000000000000000000000000000000000000'),
                           pay_amount=Wad.from_number(0.2),
                           buy_token=Address('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'),
                           buy_amount=Wad.from_number(170)))

print(idex_api.get_orders('DAI_ETH'))
exit(-1)

for order in idex_api.get_orders('DAI_ETH'):
    idex_api.cancel_order(order)
print(idex_api.get_orders('DAI_ETH'))
exit(-1)

print(idex_api.next_nonce())
print(idex_api.get_orders('DAI_ETH'))
