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

import math
import time
import logging

from web3 import Web3
from typing import List, Tuple, Optional
from hexbytes import HexBytes

from eth_abi import encode_abi
from eth_abi.packed import encode_abi_packed

from pyexchange.uniswapv3_calldata_params import BurnParams, CollectParams, DecreaseLiquidityParams, \
    IncreaseLiquidityParams, MintParams, ExactInputSingleParams, ExactInputParams, ExactOutputSingleParams, \
    ExactOutputParams, Params
from pyexchange.uniswapv3_entities import Pool, Position, Trade, Route, PriceFraction, Fraction
from pymaker import Calldata, Contract, Address, Transact, Wad, Receipt
from pymaker.approval import directly
from pymaker.model import Token
from pymaker.token import ERC20Token, NFT
from pymaker.util import bytes_to_hexstring

# TODO: move this elsewhere when LogEvent location is determined
from eth_abi.codec import ABICodec
from eth_abi.registry import registry as default_registry
from web3._utils.events import get_event_data
from web3.types import EventData

from pyexchange.uniswapv3_logs import LogIncreaseLiquidity, LogDecreaseLiquidity, LogCollect
from pyexchange.uniswapv3_math import encodeSqrtRatioX96


class PermitOptions:

    # TODO: handle selfPermit vs selfPermitAllowed options
    def __init__(self, v: int, r: str, s: str, amount: int, deadline: int):
        assert isinstance(v, int)
        assert isinstance(r, str)
        assert isinstance(s, str)
        assert isinstance(amount, int)
        assert isinstance(deadline, int)


class Permit:
    """ https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/selfPermit.ts """

    # TODO: generalize usage with calldata_params
    def encode_calldata(self, web3: Web3, fn_signature: str, arguments: List, contract_abi) -> Calldata:
        """ encode inputted contract and methods with call arguments as pymaker.Calldata """
        assert isinstance(web3, Web3)
        assert isinstance(fn_signature, str)
        assert isinstance(arguments, List)

        # TODO: add Invocation support
        return Calldata.from_contract_abi(web3, fn_signature, arguments, contract_abi)

    def encode_permit(self, token: Token, permit_options: PermitOptions, web3: Web3, abi: List) -> Calldata:
        is_allowed_permit = 'nonce' in permit_options

        self_permit_method = "selfPermit(address,uint256,uint256,uint8,bytes32,bytes32)"
        self_permit_allowed_method = "selfPermitAllowed(address,uint256,uint256,uint8,bytes32,bytes32)"

        if is_allowed_permit:
            permit_allowed_calldata = self.encode_calldata(web3, self_permit_allowed_method, [
                token.address.address,
                HexBytes(permit_options.nonce),
                HexBytes(permit_options.expiry),
                permit_options.v,
                permit_options.r,
                permit_options.s
            ], abi)
            return permit_allowed_calldata
        else:
            permit_calldata = self.encode_calldata(web3, self_permit_method, [permit_options], abi)
            return permit_calldata


# TODO: add registering keys directly to SwapRouter?
# TODO: Inherit from permit class as well
class SwapRouter(Contract):
    """ Class to handle any interactions with UniswapV3 SwapRouter
    
    Code for SwapRouter.sol: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/SwapRouter.sol
    Code for Quoter.sol: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/lens/Quoter.sol
    """

    SwapRouter_abi = Contract._load_abi(__name__, 'abi/SwapRouter.abi')['abi']
    Quoter_abi = Contract._load_abi(__name__, 'abi/Quoter.abi')['abi']

    logger = logging.getLogger()

    def __init__(self, web3: Web3, swap_router_address: Address, quoter_address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(swap_router_address, Address))
        assert(isinstance(quoter_address, Address))

        self.web3 = web3
        self.swap_router_address = swap_router_address
        self.swap_router_contract = self._get_contract(self.web3, self.SwapRouter_abi, self.swap_router_address)

        # quoter implemented for simple use cases.
        ## This doesn't account for slippage or front running, as it is executed at the current chain state,
        ## and will introduce an additional time delay into client actions while the call is processed.
        self.quoter_address = quoter_address
        self.quoter_contract = self._get_contract(self.web3, self.Quoter_abi, self.quoter_address)

    def approve(self, token: Token):
        assert (isinstance(token, Token))

        erc20_token = ERC20Token(self.web3, token.address)

        approval_function = directly()
        return approval_function(erc20_token, self.swap_router_address, 'SwapRouter')

    # TODO: move this to route entity
    @staticmethod
    def encode_route_to_path(route: Route, exact_output: bool) -> str:
        """ Convert a route to a hex encoded path"""
        assert(isinstance(route, Route))
        assert (isinstance(exact_output, bool))

        route_input_token = route.input

        path_to_encode = {}
        path_to_encode["input_token"] = route_input_token

        for i, pool in enumerate(route.pools):
            output_token = pool.token_1 if pool.token_0 == path_to_encode["input_token"] else pool.token_0
            if i == 0:
                path_to_encode["input_token"] = output_token
                path_to_encode["types"] = ['address','uint24','address']
                path_to_encode["path"] = [route_input_token.address.address, pool.fee, output_token.address.address]
            else:
                path_to_encode["input_token"] = output_token
                path_to_encode["types"] = path_to_encode["types"] + ['uint24','address']
                path_to_encode["path"] = path_to_encode["path"] + [pool.fee, output_token.address.address]

        # encode
        if exact_output:
            path_to_encode["types"].reverse()
            path_to_encode["path"].reverse()

        encoded_path = encode_abi_packed(path_to_encode["types"], path_to_encode["path"])
        encoded_path_test = Web3.test_pack_encoder(path_to_encode["types"], path_to_encode["path"])

        return bytes_to_hexstring(encoded_path)

    # https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/interfaces/IQuoter.sol
    def quote_exact_input_single(self, token_0: Token, token_1: Token, fee: int, amount_in: int, sqrt_price_limit: int) -> int:
        """ returns the amount of tokens that would be received for a given input on a path """
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)
        assert isinstance(fee, int)
        assert isinstance(amount_in, int)
        assert isinstance(sqrt_price_limit, int)

        amount_out = self.quoter_contract.functions.quoteExactInputSingle(token_0.address.address, token_1.address.address, fee, amount_in, sqrt_price_limit).call()
        return amount_out

    def quote_exact_input(self, path: str, amount_in: int) -> int:
        """ Given a hex encoded path, and a desired amount_in, return the required amount_out """
        assert isinstance(path, str)
        assert isinstance(amount_in, int)

        amount_out = self.quoter_contract.functions.quoteExactInput(path, amount_in).call()
        return amount_out

    def quote_exact_output_single(self, token_0: Token, token_1: Token, fee: int, amount_out: int, sqrt_price_limit: int) -> int:
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)
        assert isinstance(fee, int)
        assert isinstance(amount_out, int)
        assert isinstance(sqrt_price_limit, int)

        amount_in = self.quoter_contract.functions.quoteExactOutputSingle(token_0.address.address, token_1.address.address,
                                                                          fee, amount_out, sqrt_price_limit).call()
        return amount_in

    def quote_exact_output(self, path: str, amount_out: int) -> int:
        """ Given a hex encoded path, and a desired amount_out, return the required amount_in"""
        assert isinstance(path, str)
        assert isinstance(amount_out, int)

        amount_in = self.quoter_contract.functions.quoteExactInput(path, amount_out).call()
        return amount_in

    def multicall(self, calldata: List[bytes]) -> Transact:
        """ multicall takes as input List[bytes[]] corresponding to each method call to be bundled """
        assert(isinstance(calldata, List))

        return Transact(self, self.web3, self.SwapRouter_abi, self.swap_router_address, self.swap_router_contract,
                        'multicall', [calldata])

    def swap_exact_output(self, params: ExactOutputParams) -> Transact:
        """ Swap for a specified output amount across multiple pools """
        assert(isinstance(params, ExactOutputParams))

        return Transact(self, self.web3, self.SwapRouter_abi, self.swap_router_address, self.swap_router_contract,
                        "exactOutput", [tuple(params.calldata_args)])

    def swap_exact_output_single(self, params: ExactOutputSingleParams) -> Transact:
        """ Swap for a specified output amount in one pool hop """
        assert(isinstance(params, ExactOutputSingleParams))

        return Transact(self, self.web3, self.SwapRouter_abi, self.swap_router_address, self.swap_router_contract,
                        "exactOutputSingle", [tuple(params.calldata_args)])

    def swap_exact_input(self, params: ExactInputParams) -> Transact:
        """ Given an exact set of inputs, execute swap to target outputs """
        assert(isinstance(params, ExactInputParams))

        return Transact(self, self.web3, self.SwapRouter_abi, self.swap_router_address, self.swap_router_contract,
                        "exactInput", [tuple(params.calldata_args)])

    def swap_exact_input_single(self, params: ExactInputSingleParams) -> Transact:
        """ Given an exact input, execute a swap to target output """
        assert(isinstance(params, ExactInputSingleParams))

        return Transact(self, self.web3, self.SwapRouter_abi, self.swap_router_address, self.swap_router_contract,
                        "exactInputSingle", [tuple(params.calldata_args)])

    def __repr__(self):
        return f"UniswapV3SwapRouter"


# TODO: add inheritance from Permit
class PositionManager(Contract):
    """

    NFTPositionManager: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol

    """

    NonfungiblePositionManager_abi = Contract._load_abi(__name__, 'abi/NonfungiblePositionManager.abi')['abi']
    UniswapV3Factory_abi = Contract._load_abi(__name__, 'abi/UniswapV3Factory.abi')['abi']
    UniswapV3Pool_abi = Contract._load_abi(__name__, 'abi/UniswapV3Pool.abi')['abi']
    UniswapV3TickLens_abi = Contract._load_abi(__name__, 'abi/UniswapV3TickLens.abi')['abi']
    weth_abi = Contract._load_abi(__name__, 'abi/WETH.abi')

    logger = logging.getLogger()

    def __init__(self, web3: Web3, nft_position_manager_address: Address, factory_address: Address, tick_lens_address: Address, weth_address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(nft_position_manager_address, Address))
        assert(isinstance(factory_address, Address))
        assert(isinstance(tick_lens_address, Address))
        assert(isinstance(weth_address, Address))

        self.web3: Web3 = web3
        self.nft_position_manager_address = nft_position_manager_address
        self.nft_position_manager_contract = self._get_contract(self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address)

        # TODO: possible to get pool address without factory?
        self.factory_address = factory_address
        self.factory_contract = self._get_contract(self.web3, self.UniswapV3Factory_abi, self.factory_address)

        self.tick_lens_address = tick_lens_address
        self.tick_lens_contract = self._get_contract(self.web3, self.UniswapV3TickLens_abi, self.tick_lens_address)

        self.weth_address = weth_address
        self.weth_contract = self._get_contract(self.web3, self.weth_abi, self.weth_address)

    def approve(self, token: Token):
        assert (isinstance(token, Token))

        erc20_token = ERC20Token(self.web3, token.address)

        approval_function = directly()
        return approval_function(erc20_token, self.nft_position_manager_address, 'NonfungiblePositionManager')

    def _set_address_order(self, token_0: Token, token_1: Token) -> Tuple:
        """ UniswapV3 expects address token_0 to be < token_1 """
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)

        # convert hexstring to int for comparison
        if int(token_0.address.address, 16) > int(token_1.address.address, 16):
            self.logger.info(f"Reversing address order")
            return token_1, token_0
        else:
            return token_0, token_1

    def create_pool(self, token_a: Token, token_b: Token, fee: int, initial_price: int) -> Optional[Transact]:
        """ instantiate new pool and initialize pool fee
            Interacts with contract method defined here: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/base/PoolInitializer.sol
        """
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))
        assert (isinstance(fee, int))
        assert (isinstance(initial_price, int))

        # check if the pool already exists

        # check if the pool has already been initalized

        # compare the input addresses and reverse if necessary
        token_a, token_b = self._set_address_order(token_a, token_b)

        create_pool_args = [
            token_a.address.address,
            token_b.address.address,
            fee,
            initial_price
        ]

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        "createAndInitializePoolIfNecessary", create_pool_args)

    def wrap_eth(self, eth_to_wrap: Wad) -> Transact:
        """ Amount of eth (in wei) to deposit into the weth contract """
        assert(isinstance(eth_to_wrap, Wad))

        return Transact(self, self.web3, self.weth_abi, self.weth_address, self.weth_contract, "deposit", [], {"value": eth_to_wrap.value})

    def decrease_liquidity(self, params: DecreaseLiquidityParams) -> Transact:
        assert(isinstance(params, DecreaseLiquidityParams))

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'decreaseLiquidity', [tuple(params.calldata_args)], None, self._get_decrease_liquidity_result_function())

    def mint(self, params: MintParams) -> Transact:
        """ Mint a new position NFT by adding liquidity to the specified tick range """
        assert(isinstance(params, MintParams))

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'mint', [tuple(params.calldata_args)], None, self._get_increase_liquidity_result_function())

    # TODO: implement && change return type to UniV3NFT
    def migrate_position(self, lp_token_address: Address) -> NFT:
        """ migrate UniV2LP tokens to a v3 NFT """
        assert (isinstance(lp_token_address, Address))

    def multicall(self, calldata: List[bytes]) -> Transact:
        """ multicall takes as input List[bytes[]] corresponding to each method call to be bundled """
        assert(isinstance(calldata, List))

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'multicall', [calldata])

    def get_pool_address(self, token_0: Token, token_1: Token, fee: int) -> Address:
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)
        assert isinstance(fee, int)

        pool_address = self.factory_contract.functions.getPool(token_0.address.address, token_1.address.address, fee).call()
        return Address(pool_address)

    def get_pool_contract(self, pool_address: Address):
        assert(isinstance(pool_address, Address))

        pool_contract = self._get_contract(self.web3, self.UniswapV3Pool_abi, pool_address)
        return pool_contract

    def get_pool_state(self, pool_contract) -> List:
        struct = pool_contract.functions.slot0().call()
        print(struct)
        return struct

    def get_pool_price(self, pool_contract) -> int:
        """ Get the current sqrt price of the given pool """
        return self.get_pool_state(pool_contract)[0]

    def get_tick_state(self, pool_contract, current_tick: int) -> List:
        """ Retrieve state information for the given tick """
        tick = pool_contract.functions.ticks(current_tick).call()
        return tick

    def get_ticks(self, pool_address: Address, tick_bitmap_index: int) -> List:
        """ Get the initialized tick state for a given pool and bitmap index,
         by calling the TickLens contract: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/lens/TickLens.sol
        """
        assert isinstance(pool_address, Address)
        assert isinstance(tick_bitmap_index, int)

        ticks = self.tick_lens_contract.functions.getPopulatedTicksInWord(pool_address.address, tick_bitmap_index).call()
        return ticks

    def get_position_info(self, token_id) -> List:
        assert isinstance(token_id, int)

        position = self.nft_position_manager_contract.functions.positions(token_id).call()
        return position

    def positions(self, token_id: int, token_0: Token, token_1: Token) -> Position:
        """ Return position information for a given positions token_id, and token pair

            pool information is retrieved with getters defined: https://github.com/Uniswap/uniswap-v3-core/blob/main/contracts/interfaces/pool/IUniswapV3PoolState.sol
        """
        assert (isinstance(token_id, int))
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)

        position = self.get_position_info(token_id)

        assert token_0.address == Address(position[2]) and token_1.address == Address(position[3])

        fee = position[4]

        pool_address = self.get_pool_address(token_0, token_1, fee)
        pool_contract = self.get_pool_contract(pool_address)
        pool_state = self.get_pool_state(pool_contract)

        price_sqrt_ratio_x96 = pool_state[0]
        tick_current = pool_state[1]

        # TODO: figure out how to dynamically retrieve bitmap index
        tick_bitmap_index = 0
        ticks = self.get_ticks(pool_address, tick_bitmap_index)

        print("pool ticks", ticks)

        # get current in range liquidity
        pool_liquidity = pool_contract.functions.liquidity().call()
        print("pool liquidity", pool_liquidity)
        pool = Pool(token_0, token_1, fee, price_sqrt_ratio_x96, pool_liquidity, tick_current, ticks)

        tick_lower = position[5]
        tick_upper = position[6]
        position_liquidity = position[7]

        return Position(pool, tick_lower, tick_upper, position_liquidity)

    # TODO: implement
    def liquidity_at_price(self, sqrt_price_x96: int) -> int:
        """ Uses equations (L = sqrt(x*y*) and sqrt_price = sqrt(y/x) """
        pass

    # NFTs are controlled by NonfungiblePositionManager
    # https://github.com/Uniswap/uniswap-v3-core/blob/main/contracts/interfaces/pool/IUniswapV3PoolState.sol#L88
    # https://www.nansen.ai/research/the-market-making-landscape-of-uniswap-v3
    def price_position(self, token_id: int, current_price: int) -> Wad:
        """ Return the Wad price of a given token_id quoted in terms of token_1 """
        assert (isinstance(token_id, int))
        assert (isinstance(current_price, int))

        position_token_0, position_token_1 = self.get_position_reserves(token_id)

        # token_0 assumed to base, token_1 assumed to be quote
        position_value = (position_token_0 * current_price) + position_token_1
        return Wad.from_number(position_value)

    def get_position_reserves(self, token_id) -> Tuple:
        """ Given a token_id, return a tuple of a positions asset x, and asset y reserves """
        assert (isinstance(token_id, int))

        position_info = self.get_position_info(token_id)

        liquidity = position_info[7]
        price_upper_tick = 1.0001 ** position_info[5]
        price_lower_tick = 1.0001 ** position_info[6]

        position_token_0 = liquidity / math.sqrt(price_upper_tick)  # L / sqrt(pUpper)
        position_token_1 = liquidity * math.sqrt(price_lower_tick)  # L * sqrt(pLower)

        return position_token_0, position_token_1

    def increase_liquidity(self, params: IncreaseLiquidityParams) -> Transact:
        """ Add liquidity to an extant position """
        assert isinstance(params, IncreaseLiquidityParams)

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'increaseLiquidity', [tuple(params.calldata_args)], None, self._get_increase_liquidity_result_function())

    def collect(self, params: CollectParams) -> Transact:
        """ Collect fees that have accrued to a given position """
        assert isinstance(params, CollectParams)

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'collect', [tuple(params.calldata_args)], None, self._get_collect_result_function())

    def burn(self, params: BurnParams) -> Transact:
        """ Burn NFT by token_id and redeem for underlying tokens """
        assert isinstance(params, BurnParams)

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'burn', params.calldata_args, None, self._get_decrease_liquidity_result_function())

    def _get_increase_liquidity_result_function(self):

        def receipt_mapper(receipt: Receipt):
            assert (isinstance(receipt, Receipt))
            return list(map(lambda log: log, LogIncreaseLiquidity.from_receipt(self.NonfungiblePositionManager_abi, receipt)))

        return receipt_mapper

    def _get_decrease_liquidity_result_function(self):

        def receipt_mapper(receipt: Receipt):
            assert (isinstance(receipt, Receipt))
            return list(map(lambda log: log, LogDecreaseLiquidity.from_receipt(self.NonfungiblePositionManager_abi, receipt)))

        return receipt_mapper

    def _get_collect_result_function(self):

        def receipt_mapper(receipt: Receipt):
            assert (isinstance(receipt, Receipt))
            return list(map(lambda log: log, LogCollect.from_receipt(self.NonfungiblePositionManager_abi, receipt)))

        return receipt_mapper

    def __repr__(self):
        return f"UniswapV3PositionManager"


# TODO: figure out which nft will handle abi loading
class UniV3NFT(NFT):
    """ Instantiate a UniswapV3 position NFT 

    Inherit from pymaker.NFT
    
    """

    def __init__(self, NFT_uri: str, token_id: int):
        pass

    def get_owner_of(self, token_id: int):
        pass

    def get_balance_of(self, owner: Address) -> Wad:
        pass

    def get_token_description(self) -> Wad:
        pass

    def get_current_price(self) -> Wad:
        pass

    def collect_fees(self):
        pass

