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
import base64
import web3
from web3 import Web3 
from pyexchange.leverj import LeverjAPI, LeverJ
from pymaker import Wad, Address
from pymaker.keys import register_private_key
import time
import urllib.request
import json

''' 
for lines 31 to 44 you need have the following information
got get a node with a port, then get an ethereum account with private key, you also need LEV, DAI, REP ethereum addresses
and finally you need to go to leverj website and create a login, they will then give you a json file that contains AccountID
apiKey, and secret, and you need to get custodian_address from leverj you also need to  which you need to fill in below 


#w3 = Web3(Web3.HTTPProvider("NodeAddressWithPort", request_kwargs={'timeout': 60}))
#w3.eth.defaultAccount = "ethAccount"
#register_private_key(w3, "PrivateKey")
#TEST_LEV_ADDRESS='LevAddress'
#TEST_DAI_ADDRESS='DaiAddress'
#TEST_REP_ADDRESS='RepAddress'
#TEST_ETH_ADDRESS='0x0000000000000000000000000000000000000000'

#leverj = LeverjAPI(w3, "LeverjWebsiteAddress", "AccountID","apiKey","secret"  ,9.5)


leverj_custodian = LeverJ(w3, custodian_address)
'''

w3 = Web3(Web3.HTTPProvider(sys.argv[1], request_kwargs={'timeout': 60}))
w3.eth.defaultAccount = sys.argv[2]
register_private_key(w3, sys.argv[3])

leverj = LeverjAPI(w3, sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], 9.5)
leverj_custodian = LeverJ(w3, Address(sys.argv[8]))



print("get balances")
print(leverj.get_balances())

print("get balances for ETH")
print(leverj.get_balance("ETH"))

print("get balances for DAI")
print(f"type of dai balance is {type(leverj.get_balance('DAI'))}")
print(leverj.get_balance("DAI"))

print("getting LEVETH instrument from get_product")
print(leverj.get_product("LEVETH"))
print(leverj.get_product("FEEETH"))
print(leverj.get_product("ETHDAI"))
#print(leverj.get_product("USDCDAI"))
print(leverj.get_product("LEVDAI"))


print("getting config")
result = leverj.get_config()

instruments = result['instruments']
#LEVETH_instrument = instruments['LEVETH']
#
print(result)
#
#print("get custodian address for either mainnet or ropsten")
#print(leverj.get_custodian_address())
#
#print("printing LEVETH_instrument")
#print(LEVETH_instrument)
#print("printing LEVETH_instrument keys")
#print(LEVETH_instrument.keys())
#print("creating new order in testing")
#newOrder = leverj.createNewOrder('buy', 0.001229, 20, LEVETH_instrument)
#tradeNewOrder = leverj.createNewOrder('buy', 0.0017145, 5, LEVETH_instrument)
#
#print(newOrder)
#
#print('sending order to test leverj')
#leverj.place_order("LEVETH", False, Wad.from_number(0.001229), Wad.from_number(20))
#
#print('sending aggressive order to trade')
#leverj.place_order(tradeNewOrder)

#try:
#    leverj.post_order(newOrder)
#except:
#    print("there was an issue sending orders")
#    print("error", sys.exc_info()[0], "occurred.")

print("orders on the platform test")
print(leverj.get_all_orders())
#
#print("orders from LEVETH")
#print(leverj.get_orders("LEVETH"))
#
#print("executions")
#print(leverj.get_trades("LEVETH",3))
#print(len(leverj.get_trades("LEVETH",3)))
#print("7 executions")
#print(leverj.get_trades("LEVETH"))

#print("trades for LEVETH")
#print(leverj.get_all_trades("LEVETH"))


#time.sleep(15)
#
#orders = leverj.get_all_orders()
#
##for order in orders:
##    order_id = order['uuid']
##    print(leverj.cancel_order(order_id))
#
#print("cancelling all orders using cancel_all_orders function")
#print(leverj.cancel_all_orders())
#


