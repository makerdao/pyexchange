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

import time
from typing import List

from pymaker import Address, Calldata, Invocation
from pymaker.model import Token
from pymaker.util import bytes_to_hexstring, int_to_bytes32
from web3 import Web3

from pyexchange.uniswapv3_entities import Pool, Position, PriceFraction, Fraction


class Params:

    def convert_to_bytes(self, calldata: Calldata) -> bytes:
        """ convert calldata to byte array """
        return calldata.as_bytes()

    def encode_calldata(self, web3: Web3, fn_signature: str, arguments: List, contract_abi) -> Calldata:
        """ encode inputted contract and methods with call arguments as pymaker.Calldata """
        assert isinstance(web3, Web3)
        assert isinstance(fn_signature, str)
        assert isinstance(arguments, List)

        # TODO: add Invocation support
        return Calldata.from_contract_abi(web3, fn_signature, arguments, contract_abi)

    # TODO: remove method if unnecessary?
    # TODO: figure out how to handle multicall calldata
    @staticmethod
    def prepare_invocation(contract_address: Address, calldata: Calldata):
        return Invocation(contract_address, calldata)

    def _deadline(self) -> int:
        """Get a predefined deadline."""
        return int(time.time()) + 1000

    # TODO: simplify conversion path from int -> hexstring
    # TODO: call self.convert_to_bytes?
    def _to_hex(self, num: int) -> str:
        return bytes_to_hexstring(int_to_bytes32(num))


class MulticallParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, calldata: List[bytes]):
        assert (isinstance(web3, Web3))
        assert (isinstance(calldata, List))

        self.web3 = web3
        # self.calldata = self.encode_multicall_calldata(calldata)

        self.method = "multicall(bytes[])"
        self.calldata = self.encode_calldata(self.web3, self.method, [calldata], contract_abi)
        print("encoded calldata", self.calldata)

    def encode_multicall_calldata(self, arguments: List[bytes]) -> bytes:
        assert isinstance(arguments, List)

        # TODO: add Invocation support
        return Calldata.from_multicall_calldata(self.web3, arguments)


class MintParams(Params):

    # https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/nonfungiblePositionManager.test.ts

    def __init__(self, web3: Web3, contract_abi: List, position: Position, recipient: Address, slippage_tolerance: Fraction, deadline: int):
        assert(isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert(isinstance(position, Position))
        assert(isinstance(recipient, Address))
        assert(isinstance(slippage_tolerance, Fraction))
        assert(isinstance(deadline, int) or (deadline is None))

        self.position = position
        self.recipient = recipient
        self.slippage_tolerance = slippage_tolerance

        self.deadline = deadline if deadline is not None else self._deadline()

        amount_0, amount_1 = self.position.mint_amounts()

        amount_0_min, amount_1_min = self.position.mint_amounts_with_slippage(slippage_tolerance)
        print("desired amounts", amount_0, amount_1)
        print("min amounts", amount_0_min, amount_1_min)

        self.calldata_args = [
            position.pool.token_0.address.address,
            position.pool.token_1.address.address,
            position.pool.fee,
            position.tick_lower,
            position.tick_upper,
            amount_0,
            amount_1,
            amount_0_min,
            amount_1_min,
            self.recipient.address,
            self.deadline
        ]
        # use structs as tuples
        # https://github.com/ethereum/web3.py/issues/829
        self.method = "mint(address,address,uint24,int24,int24,uint256,uint256,uint256,uint256,address,uint256)"
        self.calldata = self.encode_calldata(web3, self.method, [tuple(self.calldata_args)], contract_abi)
        print(self.calldata)


class BurnParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, token_id: int):
        assert(isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert(isinstance(token_id, int))

        self.token_id = token_id

        self.calldata_args = [self.token_id]
        self.method = "burn(uint256)"
        self.calldata = self.encode_calldata(web3, self.method, self.calldata_args, contract_abi)


class CollectParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, token_id: int, recipient: Address, amount_0_max: int, amount_1_max: int):
        assert(isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert(isinstance(token_id, int))
        assert isinstance(recipient, Address)
        assert isinstance(amount_0_max, int)
        assert isinstance(amount_1_max, int)

        self.web3 = web3
        self.token_id = token_id
        self.recipient = recipient
        self.amount_0_max = amount_0_max
        self.amount_1_max = amount_1_max


        self.calldata_args = [
            self.token_id,
            self.recipient.address,
            self.amount_0_max,
            self.amount_1_max
        ]
        self.method = "collect(uint256,address,uint128,uint128)"
        self.calldata = self.encode_calldata(self.web3, self.method, [tuple(self.calldata_args)], contract_abi)


class DecreaseLiquidityParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, token_id: int, liquidity: int, amount_0_min: int, amount_1_min: int, deadline: int):
        assert(isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert(isinstance(token_id, int))
        assert(isinstance(liquidity, int))
        assert(isinstance(amount_0_min, int))
        assert(isinstance(amount_1_min, int))
        assert(isinstance(deadline, int) or (deadline is None))

        self.web3 = web3
        self.token_id = token_id
        self.liquidity = liquidity
        self.amount_0_min = amount_0_min
        self.amount_1_min = amount_1_min

        self.deadline = deadline if deadline is not None else self._deadline()

        self.calldata_args = [
            self.token_id,
            self.liquidity,
            self.amount_0_min,
            self.amount_1_min,
            self.deadline
        ]
        self.method = "decreaseLiquidity(uint256,uint128,uint256,uint256,uint256)"
        self.calldata = self.encode_calldata(self.web3, self.method, [tuple(self.calldata_args)], contract_abi)


class IncreaseLiquidityParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, token_id: int, amount_0_desired: int, amount_1_desired: int, amount_0_min: int, amount_1_min: int, deadline: int):
        assert (isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert(isinstance(token_id, int))
        assert(isinstance(amount_0_desired, int))
        assert(isinstance(amount_1_desired, int))
        assert(isinstance(amount_0_min, int))
        assert(isinstance(amount_1_min, int))
        assert(isinstance(deadline, int) or (deadline is None))

        self.web3 = web3
        self.token_id = token_id
        self.amount_0_desired = amount_0_desired
        self.amount_1_desired = amount_1_desired
        self.amount_0_min = amount_0_min
        self.amount_1_min = amount_1_min

        self.deadline = deadline if deadline is not None else self._deadline()

        self.calldata_args = [
            self.token_id,
            self.amount_0_desired,
            self.amount_1_desired,
            self.amount_0_min,
            self.amount_1_min,
            self.deadline
        ]
        self.method = "increaseLiquidity(uint256,uint256,uint256,uint256,uint256,uint256)"
        self.calldata = self.encode_calldata(self.web3, self.method, [tuple(self.calldata_args)], contract_abi)


class ExactInputSingleParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, token_in: Token, token_out: Token, fee: int, recipient: Address, deadline: int, amount_in: int, amount_out_minimum: int, sqrt_price_limit_x96: int):
        assert (isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert (isinstance(token_in, Token))
        assert (isinstance(token_out, Token))
        assert (isinstance(fee, int))
        assert (isinstance(recipient, Address))
        assert (isinstance(deadline, int) or (deadline is None))
        assert (isinstance(amount_in, int))
        assert (isinstance(amount_out_minimum, int))
        assert (isinstance(sqrt_price_limit_x96, int))

        self.web3 = web3
        self.token_in = token_in
        self.token_out = token_out
        self.fee = fee
        self.recipient = recipient
        self.deadline = deadline if deadline is not None else self._deadline()
        self.amount_in = amount_in
        self.amount_out_minimum = amount_out_minimum
        self.sqrt_price_limit_x96 = sqrt_price_limit_x96

        self.calldata_args = [
            self.token_in.address.address,
            self.token_out.address.address,
            self.fee,
            self.recipient.address,
            self.deadline,
            self.amount_in,
            self.amount_out_minimum,
            self.sqrt_price_limit_x96
        ]

        self.method = "exactInputSingle(address,address,uint24,address,uint256,uint256,uint256,uint160)"
        self.calldata = self.encode_calldata(self.web3, self.method, [tuple(self.calldata_args)], contract_abi)

class ExactOutputSingleParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, token_in: Token, token_out: Token, fee: int, recipient: Address, deadline: int,
                 amount_out: int, amount_in_maximum: int, sqrt_price_limit_x96: int):
        assert (isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert (isinstance(token_in, Token))
        assert (isinstance(token_out, Token))
        assert (isinstance(fee, int))
        assert (isinstance(recipient, Address))
        assert (isinstance(deadline, int) or (deadline is None))
        assert (isinstance(amount_out, int))
        assert (isinstance(amount_in_maximum, int))
        assert (isinstance(sqrt_price_limit_x96, int))

        self.web3 = web3
        self.token_in = token_in
        self.token_out = token_out
        self.fee = fee
        self.recipient = recipient
        self.deadline = deadline if deadline is not None else self._deadline()
        self.amount_out = amount_out
        self.amount_in_maximum = amount_in_maximum
        self.sqrt_price_limit_x96 = sqrt_price_limit_x96

        self.calldata_args = [
            self.token_in.address.address,
            self.token_out.address.address,
            self.fee,
            self.recipient.address,
            self.deadline,
            self.amount_out,
            self.amount_in_maximum,
            self.sqrt_price_limit_x96
        ]

        self.method = "exactOutputSingle(address,address,uint24,address,uint256,uint256,uint256,uint160)"
        self.calldata = self.encode_calldata(self.web3, self.method, [tuple(self.calldata_args)], contract_abi)


class ExactInputParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, path: str, recipient: Address, deadline: int, amount_in: int, amount_out_minimum: int):
        assert (isinstance(web3, Web3))
        assert(isinstance(contract_abi, List))
        assert (isinstance(path, str))
        assert (isinstance(recipient, Address))
        assert(isinstance(deadline, int) or (deadline is None))
        assert (isinstance(amount_in, int))
        assert (isinstance(amount_out_minimum, int))

        self.web3 = web3
        self.path = path
        self.recipient = recipient
        self.deadline = deadline if deadline is not None else self._deadline()
        self.amount_in = amount_in
        self.amount_out_minimum = amount_out_minimum

        self.calldata_args = [
            self.path,
            self.recipient.address,
            self.deadline,
            self.amount_in,
            self.amount_out_minimum
        ]

        self.method = "exactInput(bytes,address,uint256,uint256,uint256)"
        self.calldata = self.encode_calldata(self.web3, self.method, [tuple(self.calldata_args)], contract_abi)


class ExactOutputParams(Params):

    def __init__(self, web3: Web3, contract_abi: List, path: str, recipient: Address, deadline: int, amount_out: int, amount_in_maximum: int):
        assert (isinstance(web3, Web3))
        assert (isinstance(contract_abi, List))
        assert (isinstance(path, str))
        assert (isinstance(recipient, Address))
        assert(isinstance(deadline, int) or (deadline is None))
        assert (isinstance(amount_out, int))
        assert (isinstance(amount_in_maximum, int))

        self.web3 = web3
        self.path = path
        self.recipient = recipient
        self.deadline = deadline if deadline is not None else self._deadline()
        self.amount_out = amount_out
        self.amount_in_maximum = amount_in_maximum

        self.calldata_args = [
            self.path,
            self.recipient.address,
            self.deadline,
            self.amount_out,
            self.amount_in_maximum
        ]

        self.method = "exactOutput(bytes,address,uint256,uint256,uint256)"
        self.calldata = self.encode_calldata(self.web3, self.method, [tuple(self.calldata_args)], contract_abi)

