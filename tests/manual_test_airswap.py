import time

import pprint

from web3 import HTTPProvider
from web3 import Web3

from pymaker import Address, Wad, Contract
from pymaker.approval import directly
from pyexchange.airswap import AirswapContract
from pymaker.token import DSToken


def test_all_trades():

    web3 = Web3(HTTPProvider(endpoint_uri="https://parity0.mainnet.makerfoundation.com:8545"))

    airswap_contract = AirswapContract(web3, Address('0x8fd3121013A07C57f0D69646E86E7a4880b467b7'), 500)

    pair = {
        Address('0x0000000000000000000000000000000000000000'): True,
        Address('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'): True
    }

    eth_dai_trades = airswap_contract.get_all_trades(pair, 1)

    print("airswap all trades -->")
    pprint.pprint(eth_dai_trades)


def test_our_trades():

    web3 = Web3(HTTPProvider(endpoint_uri="https://parity0.mainnet.makerfoundation.com:8545"))
    web3.eth.defaultAccount = "0x63a035B3004A65b7D8ad86e0C28776d83671FFAe"
    airswap_contract = AirswapContract(web3, Address('0x8fd3121013A07C57f0D69646E86E7a4880b467b7'), 500)

    pair = {
        Address('0x0000000000000000000000000000000000000000'): True,
        Address('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'): True
    }

    eth_dai_trades = airswap_contract.get_trades(pair, 1)

    print("airswap our trades -->")
    pprint.pprint(eth_dai_trades)

test_all_trades()
test_our_trades()
