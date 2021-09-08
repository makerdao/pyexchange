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
from pyexchange.uniswapv3_constants import FEES, TICK_SPACING, MAX_TICK, MAX_SQRT_RATIO, MIN_TICK, MIN_SQRT_RATIO, \
     MAX_UINT128
from pyexchange.uniswapv3_calldata_params import BurnParams, CollectParams, DecreaseLiquidityParams, MintParams, \
    MulticallParams
from pyexchange.uniswapv3_entities import Pool, Position, CurrencyAmount, Fraction, PriceFraction
from pyexchange.uniswapv3_math import encodeSqrtRatioX96, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, Tick
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.model import Token
from pymaker.numeric import Wad

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
USDC_KOVAN_ADDRESS = Address("0x198419c5c340e8de47ce4c0e4711a03664d42cb2")

weth_token_kovan = Token("WETH", WETH_KOVAN_ADDRESS, 18)
weth_token_mainnet = Token("WETH", mainnet_weth_address, 18)
dai_token_kovan = Token("DAI", DAI_KOVAN_ADDRESS, 18)
dai_token_mainnet = Token("DAI", DAI_MAINNET_ADDRESS, 18)
usdc_token_kovan = Token("USDC", USDC_KOVAN_ADDRESS, 6)

provider = sys.argv[1]
private_key = sys.argv[2]
account_address = Address(sys.argv[3])

http_provider = HTTPProvider(provider)
web3 = Web3(http_provider)
web3.eth.defaultAccount = Web3.toChecksumAddress(account_address.address)
register_private_key(web3, private_key)

# useful for debugging
Transact.gas_estimate_for_bad_txs = 210000

# position_manager_mainnet = PositionManager(web3, position_manager_address, factory_address, ticklens_address, mainnet_weth_address)
position_manager_kovan = PositionManager(web3, position_manager_address, factory_address, ticklens_address,
                                         WETH_KOVAN_ADDRESS)

### mainnet pool data
# weth_dai_medium_fee_pool_address_mainnet = position_manager_mainnet.get_pool_address(weth_token_mainnet, dai_token_mainnet, 3000)
# print(weth_dai_medium_fee_pool_address_mainnet)
#
# weth_dai_mainnet_pool = position_manager_mainnet.get_pool(weth_dai_medium_fee_pool_address_mainnet, weth_token_mainnet, dai_token_mainnet, 1)
# print("mainnet pool", weth_dai_mainnet_pool)


### kovan wethdai pool data
weth_dai_medium_fee_pool_address_kovan = position_manager_kovan.get_pool_address(weth_token_kovan, dai_token_kovan,
                                                                                 3000)
weth_usdc_medium_fee_pool_address_kovan = position_manager_kovan.get_pool_address(weth_token_kovan, usdc_token_kovan, 3000)
print("weth_dai kovan pool_address", weth_dai_medium_fee_pool_address_kovan)
print("weth_usdc kovan pool_address", weth_usdc_medium_fee_pool_address_kovan)

token_0_kovan_wethdai, token_1_kovan_wethdai = position_manager_kovan._set_address_order(weth_token_kovan, dai_token_kovan)
token_0_kovan_wethusdc, token_1_kovan_wethusdc = position_manager_kovan._set_address_order(weth_token_kovan, usdc_token_kovan)

weth_dai_kovan_pool = position_manager_kovan.get_pool(weth_dai_medium_fee_pool_address_kovan, token_0_kovan_wethdai,
                                                      token_1_kovan_wethdai, 42)
weth_usdc_kovan_pool = position_manager_kovan.get_pool(weth_usdc_medium_fee_pool_address_kovan, token_0_kovan_wethusdc,
                                                      token_1_kovan_wethusdc, 42)
print("wethdai kovan pool", weth_dai_kovan_pool)
print("wethdai kovan pool liquidity", weth_dai_kovan_pool.liquidity)
print("wethusdc kovan pool liquidity", weth_usdc_kovan_pool.liquidity)

# mint liquidity wethdai kovan
def mint_weth_dai_kovan():
    kovan_weth_balance = ERC20Token(web3=web3, address=weth_token_kovan.address).balance_of(account_address)
    kovan_dai_balance = ERC20Token(web3=web3, address=dai_token_kovan.address).balance_of(account_address)

    desired_lower_tick = Tick.nearest_usable_tick(
        weth_dai_kovan_pool.tick_current - (weth_dai_kovan_pool.tick_spacing * 5), weth_dai_kovan_pool.tick_spacing)
    desired_upper_tick = Tick.nearest_usable_tick(
        weth_dai_kovan_pool.tick_current + (weth_dai_kovan_pool.tick_spacing * 3), weth_dai_kovan_pool.tick_spacing)
    slippage_tolerance = Fraction(2, 100)
    deadline = int(time.time() + 1000)

    weth_to_add = kovan_weth_balance / Wad.from_number(2)
    dai_to_add = kovan_dai_balance / Wad.from_number(2)
    kovan_position_to_mint = Position.from_amounts(weth_dai_kovan_pool, desired_lower_tick, desired_upper_tick,
                                                   weth_to_add.value, dai_to_add.value, False)

    print("position_to_mint liquidity", kovan_position_to_mint.liquidity)

    # approve kovan tokens for usage by PositionManager
    position_manager_kovan.approve(weth_token_kovan)
    position_manager_kovan.approve(dai_token_kovan)

    kovan_mint_params = MintParams(web3, NonfungiblePositionManager_abi, kovan_position_to_mint, account_address,
                                   slippage_tolerance, deadline)
    kovan_mint_receipt = position_manager_kovan.mint(kovan_mint_params).transact()

    assert kovan_mint_receipt is not None and kovan_mint_receipt.successful
    print("tx receipt", kovan_mint_receipt.transaction_hash.hex())

def multicall_collect_burn_wethdai_kovan(token_id):
     position_to_burn = position_manager_kovan.positions(token_id, weth_dai_kovan_pool.token_0, weth_dai_kovan_pool.token_1)

     deadline = int(time.time() + 1000)

     token_0_amount = position_to_burn.token_0_amount if position_to_burn.token_0_amount is not None else position_to_burn.amount_in_token_0()
     token_1_amount = position_to_burn.token_1_amount if position_to_burn.token_1_amount is not None else position_to_burn.amount_in_token_1()

     # remove all liquidity in position
     decrease_liquidity_params = DecreaseLiquidityParams(web3, NonfungiblePositionManager_abi, token_id, position_to_burn.liquidity, token_0_amount.quotient(), token_1_amount.quotient(), deadline)

     # collect all fees
     amount_0_max_fee_to_collect = MAX_UINT128
     amount_1_max_fee_to_collect = MAX_UINT128
     collect_params = CollectParams(web3, NonfungiblePositionManager_abi, token_id, account_address, amount_0_max_fee_to_collect, amount_1_max_fee_to_collect)

     # burn position following liquidity removal
     burn_params = BurnParams(web3, NonfungiblePositionManager_abi, token_id)

     multicall_calldata = [
          decrease_liquidity_params.calldata.value,
          collect_params.calldata.value,
          burn_params.calldata.value
     ]

     multicall_params = MulticallParams(web3, NonfungiblePositionManager_abi, multicall_calldata).calldata.value
     multicall_receipt = position_manager_kovan.multicall([multicall_params]).transact()
     assert multicall_receipt is not None and multicall_receipt.successful

def mint_weth_usdc_kovan():

    # returned balance from balance_of shows amounts normalized to 18 decimals, so unnormalization to USDC 6 decimals is needed
     kovan_weth_balance = ERC20Token(web3=web3, address=weth_token_kovan.address).balance_of(account_address)
     kovan_usdc_balance = ERC20Token(web3=web3, address=usdc_token_kovan.address).balance_of(account_address)

     print("balance from balance_of, WETH: ", kovan_weth_balance, "USDC: ", kovan_usdc_balance)
     current_tick = weth_usdc_kovan_pool.tick_current
     current_pool_price = PriceFraction.get_price_at_tick(weth_token_kovan, usdc_token_kovan, weth_usdc_kovan_pool.tick_current)

     print("current pool tick", weth_usdc_kovan_pool.tick_current)
     print("current pool price", current_pool_price.float_quotient())

     desired_price = PriceFraction(weth_token_kovan, usdc_token_kovan, Wad.from_number(1).value, usdc_token_kovan.unnormalize_amount(Wad.from_number(2800)).value)
     desired_tick = PriceFraction.get_tick_at_price(desired_price)
     print("desired tick and price", desired_tick, desired_price.float_quotient())

     desired_lower_tick = Tick.nearest_usable_tick(
          desired_tick - (weth_usdc_kovan_pool.tick_spacing * 5), weth_usdc_kovan_pool.tick_spacing)
     desired_upper_tick = Tick.nearest_usable_tick(
          desired_tick + (weth_usdc_kovan_pool.tick_spacing * 3), weth_usdc_kovan_pool.tick_spacing)
     slippage_tolerance = Fraction(2, 100)
     deadline = int(time.time() + 1000)

     # weth_to_add = kovan_weth_balance / Wad.from_number(2)
     # usdc_to_add = usdc_token_kovan.normalize_amount(kovan_usdc_balance) / Wad.from_number(2)
     weth_to_add = kovan_weth_balance / Wad.from_number(2)
     usdc_to_add = kovan_usdc_balance / Wad.from_number(2)

     print("pool token 0: ", weth_usdc_kovan_pool.token_0.name)

     print("weth to add: ", weth_to_add, "usdc to add: ", usdc_to_add)
     kovan_position_to_mint = Position.from_amounts(weth_usdc_kovan_pool, desired_lower_tick, desired_upper_tick,
                                                    usdc_to_add.value, weth_to_add.value, False)

     print("position_to_mint liquidity", kovan_position_to_mint.liquidity)

     # approve kovan tokens for usage by PositionManager
     position_manager_kovan.approve(weth_token_kovan)
     position_manager_kovan.approve(usdc_token_kovan)

     kovan_mint_params = MintParams(web3, NonfungiblePositionManager_abi, kovan_position_to_mint, account_address,
                                    slippage_tolerance, deadline)
     kovan_mint_receipt = position_manager_kovan.mint(kovan_mint_params).transact()

     assert kovan_mint_receipt is not None and kovan_mint_receipt.successful
     print("tx receipt", kovan_mint_receipt.transaction_hash.hex())

# mint_weth_dai_kovan()

# token_ids = position_manager_kovan.get_token_ids_by_address(account_address)
# print("token ids", token_ids)
# multicall_collect_burn_wethdai_kovan(token_ids[0])

# time.sleep(5)
mint_weth_usdc_kovan()

