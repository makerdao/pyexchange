# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2021 MikeHathaway
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

from pyexchange.uniswapv3 import SwapRouter, PositionManager
from pyexchange.uniswapv3_calldata_params import ExactOutputSingleParams
from pyexchange.uniswapv3_constants import TRADE_TYPE
from pyexchange.uniswapv3_entities import Fraction, Route, Trade, CurrencyAmount
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.model import Token
from pymaker.numeric import Wad

SwapRouter_abi = Contract._load_abi(__name__, '../pyexchange/abi/SwapRouter.abi')['abi']

position_manager_address = Address("0xC36442b4a4522E871399CD717aBDD847Ab11FE88")
swap_router_address = Address("0xE592427A0AEce92De3Edee1F18E0157C05861564")
quoter_address = Address("0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6")
mainnet_weth_address = Address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
factory_address = Address("0x1F98431c8aD98523631AE4a59f267346ea31F984")
ticklens_address = Address("0xbfd8137f7d1516D3ea5cA83523914859ec47F573")

DAI_KOVAN_ADDRESS = Address("0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa")
DAI_MAINNET_ADDRESS = Address("0x6B175474E89094C44Da98b954EedeAC495271d0F")
WETH_KOVAN_ADDRESS = Address("0xd0a1e359811322d97991e03f863a0c30c2cf029c")

weth_token_kovan = Token("WETH", WETH_KOVAN_ADDRESS, 18)
weth_token_mainnet = Token("WETH", mainnet_weth_address, 18)
dai_token_kovan = Token("DAI", DAI_KOVAN_ADDRESS, 18)
dai_token_mainnet = Token("DAI", DAI_MAINNET_ADDRESS, 18)

# useful for debugging
Transact.gas_estimate_for_bad_txs = 210000

provider = sys.argv[1]
private_key = sys.argv[2]
account_address = sys.argv[3]

http_provider = HTTPProvider(provider)
web3 = Web3(http_provider)
web3.eth.defaultAccount = Web3.toChecksumAddress(account_address)
register_private_key(web3, private_key)

swap_router_kovan = SwapRouter(web3, swap_router_address, quoter_address)
position_manager_kovan = PositionManager(web3, position_manager_address, factory_address, ticklens_address, WETH_KOVAN_ADDRESS)

weth_dai_medium_fee_pool_address_kovan = position_manager_kovan.get_pool_address(weth_token_kovan, dai_token_kovan, 3000)
print(weth_dai_medium_fee_pool_address_kovan)

weth_dai_kovan_pool = position_manager_kovan.get_pool(weth_dai_medium_fee_pool_address_kovan, weth_token_kovan, dai_token_kovan, 42)
print("mainnet pool", weth_dai_kovan_pool)

### approve tokens for use by SwapRouter
swap_router_kovan.approve(dai_token_kovan)
swap_router_kovan.approve(weth_token_kovan)

### wrap eth to weth
# wrap_eth_receipt = position_manager_kovan.wrap_eth(Wad.from_number(.2)).transact()
# assert wrap_eth_receipt is not None and wrap_eth_receipt.successful

## swap exact output weth -> dai
# desired_amount_out = Wad.from_number(182).value
desired_amount_out = 10
slippage_tolerance = Fraction(10, 100)
deadline = int(time.time() + 1000)

print("current pool price", weth_dai_kovan_pool.get_token_1_price().quotient())

# TODO: calculate this automatically -> get current price -> convert to sqrt_price_x96 -> multiple by slippage tolerance
# calculate price limit, increasing or decreasing will depend on the asset being swapped
sqrt_price_limit = int(weth_dai_kovan_pool.square_root_ratio_x96 * (1 + slippage_tolerance.float_quotient()))

weth_dai_kovan_route = Route([weth_dai_kovan_pool], weth_dai_kovan_pool.token_0, weth_dai_kovan_pool.token_1)
trade = Trade.from_route(weth_dai_kovan_route, CurrencyAmount.from_raw_amount(weth_dai_kovan_pool.token_1, desired_amount_out), TRADE_TYPE.EXACT_OUTPUT_SINGLE.value)
max_amount_in = trade.maximum_amount_in(slippage_tolerance).quotient()
print("max amount in Trade calculation", max_amount_in)

amount_in = swap_router_kovan.quote_exact_output_single(weth_dai_kovan_pool.token_0, weth_dai_kovan_pool.token_1, weth_dai_kovan_pool.fee, desired_amount_out,
                                                       sqrt_price_limit)

print("amount in Quoter calculation", amount_in)

exact_output_single_params = ExactOutputSingleParams(web3, SwapRouter_abi, trade.route.token_path[0],
                                                     trade.route.token_path[1], trade.route.pools[0].fee, Address(web3.eth.defaultAccount),
                                                     deadline, desired_amount_out, max_amount_in, sqrt_price_limit)

swap_exact_output_receipt = swap_router_kovan.swap_exact_output_single(exact_output_single_params).transact()
assert swap_exact_output_receipt is not None and swap_exact_output_receipt.successful
