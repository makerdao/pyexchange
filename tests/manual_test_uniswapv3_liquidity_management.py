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

from lib.pymaker.pymaker.token import ERC20Token
from pyexchange.uniswapv3 import PositionManager
from pyexchange.uniswapv3_constants import FEES, TICK_SPACING, MAX_TICK, MAX_SQRT_RATIO, MIN_TICK, MIN_SQRT_RATIO
from pyexchange.uniswapv3_calldata_params import BurnParams, CollectParams, DecreaseLiquidityParams, MintParams, \
     MulticallParams
from pyexchange.uniswapv3_entities import Pool, Position, CurrencyAmount, Fraction, PriceFraction
from pyexchange.uniswapv3_math import encodeSqrtRatioX96, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, Tick
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.model import Token


NonfungiblePositionManager_abi = Contract._load_abi(__name__, '../pyexchange/abi/NonfungiblePositionManager.abi')['abi']

# Uniswap contracts are deployed to the same addresses on every network
position_manager_address = Address("0xC36442b4a4522E871399CD717aBDD847Ab11FE88")
swap_router_address = Address("0xE592427A0AEce92De3Edee1F18E0157C05861564")
factory_address = Address("0x1F98431c8aD98523631AE4a59f267346ea31F984")
ticklens_address = Address("0xbfd8137f7d1516D3ea5cA83523914859ec47F573")
mainnet_weth_address = Address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
quoter_address = Address("0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6")

DAI_KOVAN_ADDRESS = Address("0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa")
DAI_MAINNET_ADDRESS = Address("0x6B175474E89094C44Da98b954EedeAC495271d0F")
WETH_KOVAN_ADDRESS = Address("0xd0a1e359811322d97991e03f863a0c30c2cf029c")

weth_token_kovan = Token("WETH", WETH_KOVAN_ADDRESS, 18)
weth_token_mainnet = Token("WETH", mainnet_weth_address, 18)
dai_token_kovan = Token("DAI", DAI_KOVAN_ADDRESS, 18)
dai_token_mainnet = Token("DAI", DAI_MAINNET_ADDRESS, 18)

provider = sys.argv[1]
private_key = sys.argv[2]
account_address = sys.argv[3]

http_provider = HTTPProvider(provider)
web3 = Web3(http_provider)
web3.eth.defaultAccount = Web3.toChecksumAddress(account_address)
register_private_key(web3, private_key)

# position_manager_mainnet = PositionManager(web3, position_manager_address, factory_address, ticklens_address, mainnet_weth_address)
position_manager_kovan = PositionManager(web3, position_manager_address, factory_address, ticklens_address, WETH_KOVAN_ADDRESS)

### mainnet pool data
# weth_dai_medium_fee_pool_address_mainnet = position_manager_mainnet.get_pool_address(weth_token_mainnet, dai_token_mainnet, 3000)
# print(weth_dai_medium_fee_pool_address_mainnet)
#
# weth_dai_mainnet_pool = position_manager_mainnet.get_pool(weth_dai_medium_fee_pool_address_mainnet, weth_token_mainnet, dai_token_mainnet, 1)
# print("mainnet pool", weth_dai_mainnet_pool)


### kovan pool data
weth_dai_medium_fee_pool_address_kovan = position_manager_kovan.get_pool_address(weth_token_kovan, dai_token_kovan, 3000)
print(weth_dai_medium_fee_pool_address_kovan)

weth_dai_kovan_pool = position_manager_kovan.get_pool(weth_dai_medium_fee_pool_address_kovan, weth_token_kovan, dai_token_kovan, 42)
print("mainnet pool", weth_dai_kovan_pool)


# mint liquidity kovan
kovan_weth_balance = ERC20Token(web3=web3, address=weth_token_kovan.address).balance_of(account_address)
kovan_dai_balace = ERC20Token(web3=web3, address=weth_token_kovan.address).balance_of(account_address)

desired_lower_tick = Tick.nearest_usable_tick(weth_dai_kovan_pool.tick_current - (weth_dai_kovan_pool.tick_spacing * 5), weth_dai_kovan_pool.tick_spacing)
desired_upper_tick = Tick.nearest_usable_tick(weth_dai_kovan_pool.tick_current + (weth_dai_kovan_pool.tick_spacing * 3), weth_dai_kovan_pool.tick_spacing)
slippage_tolerance = Fraction(20, 100)
deadline = int(time.time() + 1000)

kovan_position_to_mint = Position.from_amounts(weth_dai_kovan_pool, desired_lower_tick, desired_upper_tick, kovan_weth_balance / 2, kovan_dai_balace / 2, False)

# approve kovan tokens for usage by PositionManager
position_manager_kovan.approve(weth_token_kovan)
position_manager_kovan.approve(dai_token_kovan)

kovan_mint_params = MintParams(web3, NonfungiblePositionManager_abi, kovan_position_to_mint, account_address, slippage_tolerance, deadline)
kovan_mint_receipt = position_manager_kovan.mint(kovan_mint_params).transact()

assert kovan_mint_receipt is not None and kovan_mint_receipt.successful
