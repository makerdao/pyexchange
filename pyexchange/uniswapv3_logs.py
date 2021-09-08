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

from hexbytes import HexBytes
from typing import List
from pymaker import Receipt

from eth_abi.codec import ABICodec
from eth_abi.registry import registry as default_registry
from web3._utils.events import get_event_data
from web3.types import EventData


class LogInitialize:
    """ seth keccak $(seth --from-ascii "Initialize(uint160,int24)") == 0x98636036cb66a9c19a37435efc1e90142190214e8abeb821bdba3f2990dd4c95
        Initialize is defined in uniswap-v3-core: https://github.com/Uniswap/uniswap-v3-core/blob/main/contracts/interfaces/pool/IUniswapV3PoolEvents.sol

    """
    def __init__(self, log):
        self.sqrt_price_x96 = log["args"]["sqrtPriceX96"]
        self.tick = log["args"]["tick"]

    @classmethod
    def from_receipt(cls, contract_abi: List, receipt: Receipt):
        assert (isinstance(contract_abi, List))
        assert (isinstance(receipt, Receipt))

        initialize_logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                if len(log['topics']) > 0 and log['topics'][0] == HexBytes('0x98636036cb66a9c19a37435efc1e90142190214e8abeb821bdba3f2990dd4c95'):
                    log_initialize_abi = [abi for abi in contract_abi if abi.get('name') == 'Initialize'][0]
                    codec = ABICodec(default_registry)
                    event_data = get_event_data(codec, log_initialize_abi, log)

                    initialize_logs.append(LogInitialize(event_data))

        return initialize_logs


class LogMint:
    """ seth keccak $(seth --from-ascii "Mint(address,address,int24,int24,uint128,uint256,uint256)") == 0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde

        Mint is defined in uniswap-v3-core: https://github.com/Uniswap/uniswap-v3-core/blob/main/contracts/interfaces/pool/IUniswapV3PoolEvents.sol
    """
    def __init__(self, log):
        self.sender = log["args"]["sender"]
        self.owner = log["args"]["owner"]
        self.tick_lower = log["args"]["tickLower"]
        self.tick_upper = log["args"]["tickUpper"]
        self.liquidity = log["args"]["amount"]
        self.amount_0 = log["args"]["amount0"]
        self.amount_1 = log["args"]["amount1"]

    @classmethod
    def from_receipt(cls, contract_abi: List, receipt: Receipt):
        assert (isinstance(contract_abi, List))
        assert (isinstance(receipt, Receipt))

        mint_logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                if len(log['topics']) > 0 and log['topics'][0] == HexBytes('0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde'):
                    log_mint_abi = [abi for abi in contract_abi if abi.get('name') == 'Mint'][0]
                    codec = ABICodec(default_registry)
                    event_data = get_event_data(codec, log_mint_abi, log)

                    mint_logs.append(LogMint(event_data))

        return mint_logs


class LogIncreaseLiquidity:
    """ seth keccak $(seth --from-ascii "IncreaseLiquidity(uint256,uint128,uint256,uint256)") == 0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f

        mint and increaseLiquidity methods emit the same IncreaseLiquidity event
    """
    def __init__(self, log):
        self.token_id = log["args"]["tokenId"]
        self.liquidity = log["args"]["liquidity"]
        self.amount_0 = log["args"]["amount0"]
        self.amount_1 = log["args"]["amount1"]

    @classmethod
    def from_receipt(cls, contract_abi: List, receipt: Receipt):
        assert (isinstance(contract_abi, List))
        assert (isinstance(receipt, Receipt))

        liquidity_logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                if len(log['topics']) > 0 and log['topics'][0] == HexBytes('0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f'):
                    log_increase_liquidity_abi = [abi for abi in contract_abi if abi.get('name') == 'IncreaseLiquidity'][0]
                    codec = ABICodec(default_registry)
                    event_data = get_event_data(codec, log_increase_liquidity_abi, log)

                    liquidity_logs.append(LogIncreaseLiquidity(event_data))

        return liquidity_logs


class LogDecreaseLiquidity:
    """ seth keccak $(seth --from-ascii "DecreaseLiquidity(uint256,uint128,uint256,uint256)") == 0x26f6a048ee9138f2c0ce266f322cb99228e8d619ae2bff30c67f8dcf9d2377b4

        burn and decreaseLiquidity methods emit the same DecreaseLiquidity event
    """
    def __init__(self, log):
        self.token_id = log["args"]["tokenId"]
        self.liquidity = log["args"]["liquidity"]
        self.amount_0 = log["args"]["amount0"]
        self.amount_1 = log["args"]["amount1"]

    @classmethod
    def from_receipt(cls, contract_abi: List, receipt: Receipt):
        assert (isinstance(contract_abi, List))
        assert (isinstance(receipt, Receipt))

        liquidity_logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                if len(log['topics']) > 0 and log['topics'][0] == HexBytes(
                        '0x26f6a048ee9138f2c0ce266f322cb99228e8d619ae2bff30c67f8dcf9d2377b4'):
                    log_decrease_liquidity_abi = [abi for abi in contract_abi if abi.get('name') == 'DecreaseLiquidity'][0]
                    codec = ABICodec(default_registry)
                    event_data = get_event_data(codec, log_decrease_liquidity_abi, log)

                    liquidity_logs.append(LogDecreaseLiquidity(event_data))

        return liquidity_logs


class LogCollect:
    """ seth keccak $(seth --from-ascii "Collect(uint256,address,uint256,uint256)") == 0x40d0efd1a53d60ecbf40971b9daf7dc90178c3aadc7aab1765632738fa8b8f01
    """
    def __init__(self, log):
        self.token_id = log["args"]["tokenId"]
        self.recipient = log["args"]["recipient"]
        self.amount_0 = log["args"]["amount0"]
        self.amount_1 = log["args"]["amount1"]

    @classmethod
    def from_receipt(cls, contract_abi: List, receipt: Receipt):
        assert (isinstance(contract_abi, List))
        assert (isinstance(receipt, Receipt))

        liquidity_logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                if len(log['topics']) > 0 and log['topics'][0] == HexBytes(
                        '0x40d0efd1a53d60ecbf40971b9daf7dc90178c3aadc7aab1765632738fa8b8f01'):
                    log_collect_abi = [abi for abi in contract_abi if abi.get('name') == 'Collect'][0]
                    codec = ABICodec(default_registry)
                    event_data = get_event_data(codec, log_collect_abi, log)

                    liquidity_logs.append(LogCollect(event_data))

        return liquidity_logs


class LogSwap:
    """ seth keccak $(seth --from-ascii "Swap(address,address,int256,int256,uint160,uint128,int24)") == 0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67
    """
    def __init__(self, log):
        self.sender = log["args"]["sender"]
        self.owner = log["args"]["recipient"]
        self.amount_0 = log["args"]["amount0"]
        self.amount_1 = log["args"]["amount1"]
        self.sqrt_price_x96 = log["args"]["sqrtPriceX96"]
        self.liquidity = log["args"]["liquidity"]
        self.tick = log["args"]["tick"]

    @classmethod
    def from_receipt(cls, contract_abi: List, receipt: Receipt):
        assert (isinstance(contract_abi, List))
        assert (isinstance(receipt, Receipt))

        swap_logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                if len(log['topics']) > 0 and log['topics'][0] == HexBytes(
                        '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67'):
                    log_swap_abi = [abi for abi in contract_abi if abi.get('name') == 'Swap'][0]
                    codec = ABICodec(default_registry)
                    event_data = get_event_data(codec, log_swap_abi, log)

                    swap_logs.append(LogSwap(event_data))

        return swap_logs
