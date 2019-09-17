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
#from pyexchange.coinbase import CoinbaseApi
from web3 import Web3 
from pyexchange.leverj import LeverjAPI, LeverJ
from pymaker import Wad, Address
from pymaker.keys import register_private_key
import time
import urllib.request
import json

w3 = Web3(Web3.HTTPProvider("https://ropsten.infura.io/v3/351c78ed30774d93b247c588ec019a34", request_kwargs={'timeout': 60}))
w3.eth.defaultAccount = "0x3b0194e96c57dd9cFb839720080b5626718C0E48"
register_private_key(w3, "DC2CBC1873E77E824E538B8CD591268831759BBBDE2CC6C56076379552899BA5")
TEST_LEV_ADDRESS='0xAa7127e250E87476FdD253f15e86A4Ea9c4c4BD4'
TEST_DAI_ADDRESS='0xb0F776EB352738CF25710d92Fca2f4A5e2c24D3e'
TEST_ETH_ADDRESS='0x0000000000000000000000000000000000000000'

leverj = LeverjAPI(w3, "https://test.leverj.io", "0x3b0194e96c57dd9cFb839720080b5626718C0E48","0x376E7631ef8ABd2685904bB5Ab16Cd8D2C51E862","0xf41c425f1a6b9b0e57ebad73cc01a65a2c9c2acc5f3327acf8930f0dbc74f230"  ,9.5)

custodian_address =  Address("0xD5727f9d8C5b9E4472566683F4e562Ef9B47dCE3")


leverj_custodian = LeverJ(w3, custodian_address)

#print(leverj_custodian.withdraw_token(leverj, TEST_LEV_ADDRESS, 400000))
#claim_funds = leverj_custodian.claim_funds(leverj, TEST_ETH_ADDRESS,400000000).transact()
#print(claim_funds.transaction_hash.hex())
#print(claim_funds.successful)


#first_approval = leverj_custodian.approve_token(TEST_DAI_ADDRESS, 400000).transact()
#print(first_approval.__dict__)
#print(first_approval.transaction_hash.hex())
#print("above is about first approval")
#print(" ")
#print("Now we will send some LEV/DAI to custodian contract")
#first_lev_deposit =  leverj_custodian.deposit_token(TEST_DAI_ADDRESS, 400000).transact()
#print(first_lev_deposit.successful)
#print(first_lev_deposit.transaction_hash.hex())
#print("above is the first lev deposit to custodian contract")
#
#
#
#first_transact = leverj_custodian.deposit_ether(Wad.from_number(0.01)).transact()
#print(first_transact.successful)
#print(first_transact.transaction_hash.hex())
#second_transact = leverj_custodian.deposit_ether(Wad.from_number(0.02)).transact()
#print(second_transact.successful)
#print(second_transact.transaction_hash.hex())
#


print("get balances")
print(leverj.get_balances())

print("get balances for ETH")
print(leverj.get_balance("ETH"))

print("get balances for DAI")
print(leverj.get_balance("DAI"))

print("getting LEVETH instrument from get_product")
print(leverj.get_product("LEVETH"))


print("getting config")
result = leverj.get_config()

instruments = result['instruments']
#LEVETH_instrument = instruments['LEVETH']
#
#print(result)
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
#leverj.place_order(newOrder)
#
#print('sending aggressive order to trade')
#leverj.place_order(tradeNewOrder)

#try:
#    leverj.post_order(newOrder)
#except:
#    print("there was an issue sending orders")
#    print("error", sys.exc_info()[0], "occurred.")

#print("orders on the platform test")
#print(leverj.get_all_orders())
#
#print("orders from LEVETH")
#print(leverj.get_orders("LEVETH"))
#
#print("executions")
#print(leverj.get_trades("LEVETH",3))
#print(len(leverj.get_trades("LEVETH",3)))
#print("7 executions")
#print(leverj.get_trades("LEVETH",7))
#
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








