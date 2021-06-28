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


##############################

# SWAP is nodelegatecall
## uniswapv3 router simply acts to calculate the exact input amounts, and generate a callback, that can be retrieved by the front end and then used to seperately call out to the pool contract.
## unlike univ2 there's msg.sender is only used to check implementation of IUniswapV3SwapCallback interface. Recipient is otherwise available as a callback param

# other pool functions are open
## contracts can call mint, burn, collect for position management and fee collection.
## Fees need to be manually collected by NFT holder.

# TODO:
## update pool token liquidator to call removeLiquidity() directly on router, and then transfer instead of transerFrom as tokens are now hold by the smart contract.
## This will reduce the number of approvals, but would require transfering lp tokens to the contract first

# Additional guides: https://blog.openzeppelin.com/ethereum-in-depth-part-2-6339cf6bddb9/

import time

from web3 import Web3
from typing import List, Tuple
from hexbytes import HexBytes

from pyexchange.uniswapv3_calldata_params import BurnParams, CollectParams, DecreaseLiquidityParams, \
    IncreaseLiquidityParams, MintParams, ExactInputSingleParams, ExactInputParams, ExactOutputSingleParams, \
    ExactOutputParams
from pyexchange.uniswapv3_entities import Pool, Position
from pymaker import Calldata, Contract, Address, Transact, Wad, Receipt
from pymaker.approval import directly
from pymaker.model import Token
from pymaker.token import ERC20Token, NFT

# TODO: move this elsewhere when LogEvent location is determined
from eth_abi.codec import ABICodec
from eth_abi.registry import registry as default_registry
from web3._utils.events import get_event_data
from web3.types import EventData

# TODO: figure out division of responsibiliies between uniswapv3_entitites.Pool and UniswapV3
from pyexchange.uniswapv3_math import encodeSqrtRatioX96


class UniswapV3(Contract):
    """
    UniswapV3 Python Client

    Each UniswapV3 instance is intended to be used with a single token pair at a time. 
    Multiple fee pools per token pair are supported.


    Interacting with pool, router, and if deploying a new pool, factory contracts.
    Pool: https://github.com/Uniswap/uniswap-v3-core/blob/main/contracts/UniswapV3Pool.sol

    Documentation is available here: https://docs.uniswap.org/concepts/V3-overview/glossary
    """

    # IUniswapV3Pool_abi = Contract._load_abi(__name__, 'abi/IUniswapV3Pool.abi')['abi']

    def __init__(self, web3: Web3, token_a: Token, token_b: Token, keeper_address: Address, swap_router_address: Address, factory_address: Address, pool_fee: Wad):
        assert (isinstance(web3, Web3))
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))
        assert (isinstance(keeper_address, Address))
        assert (isinstance(swap_router_address, Address))
        assert (isinstance(factory_address, Address))
        assert (isinstance(pool_fee, Wad))

        self.web3 = web3
        self.pool_fee = pool_fee
        self.token_a = token_a
        self.token_b = token_b

    def get_pool_balance_of_token(self, token: Token, pool_address: Address) -> Wad:
        assert (isinstance(token, Token))
        assert (isinstance(pool_address, Address))

        return token.normalize_amount(ERC20Token(web3=self.web3, address=token.address).balance_of(pool_address))

    def get_account_token_balance(self, token: Token) -> Wad:
        assert (isinstance(token, Token))

        return token.normalize_amount(ERC20Token(web3=self.web3, address=token.address).balance_of(self.account_address))

    def get_account_eth_balance(self) -> Wad:
        return Wad.from_number(Web3.fromWei(self.web3.eth.getBalance(self.account_address.address), 'ether'))

    # TODO: determine if other abstractions should be used instead
    def get_pool_info(self):
        """ call slot0 which stores current price, tick, fees, and oracle information for a pool"""
        pool.get_pool_info()

    def observe_price(self, seconds_ago: int) -> Wad:
        """ observe price over specified number of seconds  """
        assert (isinstance(seconds_ago, int))

        # TODO: finish implementing
        return Wad.from_number(pool_contract.functions.observe(seconds_ago).call())


# TODO: add registering keys directly to SwapRouter?
class SwapRouter(Contract):
    """ Class to handle any interactions with UniswapV3 SwapRouter
    
    Code for SwapRouter.sol: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/SwapRouter.sol
    """

    SwapRouter_abi = Contract._load_abi(__name__, 'abi/SwapRouter.abi')['abi']

    def __init__(self, web3: Web3, swap_router_address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(swap_router_address, Address))

        self.swap_router_address = swap_router_address
        self.swap_router_contract = self._get_contract(self.uniswap_pool.web3, self.Iswap_router_abi, self.swap_router_address)

    # state machine - given route and trades to execute, return transact
    def determine_swap_method(self, trade, route) -> Transact:
        pass

    def swap_exact_output(self, params: ExactOutputParams) -> Transact:
        assert(isinstance(params, ExactOutputParams))

        return Transact(self, self.web3, self.swap_router_abi, self.swap_router_address, self.swap_router_contract,
                        "exactOutput", [tuple(params.calldata_args)])

    def swap_exact_output_single(self, params: ExactOutputSingleParams) -> Transact:
        assert(isinstance(params, ExactOutputSingleParams))

        return Transact(self, self.web3, self.swap_router_abi, self.swap_router_address, self.swap_router_contract,
                        "exactOutputSingle", [tuple(params.calldata_args)])

    def swap_exact_input(self, params: ExactInputParams) -> Transact:
        """ Given an exact set of inputs, execute swap to target outputs """
        assert(isinstance(params, ExactInputParams))

        return Transact(self, self.web3, self.swap_router_abi, self.swap_router_address, self.swap_router_contract,
                        "exactInput", [tuple(params.calldata_args)])

    def swap_exact_input_single(self, params: ExactInputSingleParams) -> Transact:
        """ Given an exact input, execute a swap to target output """
        assert(isinstance(params, ExactInputSingleParams))

        return Transact(self, self.web3, self.swap_router_abi, self.swap_router_address, self.swap_router_contract,
                        "exactInputSingle", [tuple(params.calldata_args)])


# TODO: move this to pymaker and add tests
# TODO: paramaterize abi as well, as opposed to hardcoding to position manager
# TODO: figure out how to handle arbitrary event shapes -> conform to common interface (from_log)
class LogEvent:
    """ subclass this method with a given events shape """
    @staticmethod
    def from_event_data(self, event_data: EventData):
        assert (isinstance(event_data, EventData))
        raise NotImplementedError


# TODO: make this generalizable?
class LogMint:
    """ seth keccak $(seth --from-ascii "IncreaseLiquidity(uint256,uint128,uint256,uint256)") == 0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f """
    def __init__(self, log):
        self.token_id = log["args"]["tokenId"]
        self.liquidity = log["args"]["liquidity"]
        self.amount_0 = log["args"]["amount0"]
        self.amount_1 = log["args"]["amount1"]

    @classmethod
    def from_receipt(cls, receipt: Receipt):
        assert (isinstance(receipt, Receipt))

        liquidity_logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                if len(log['topics']) > 0 and log['topics'][0] == HexBytes('0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f'):
                    log_token_a_transfer_out_abi = [abi for abi in PositionManager.NonfungiblePositionManager_abi if abi.get('name') == 'IncreaseLiquidity'][0]
                    codec = ABICodec(default_registry)
                    event_data = get_event_data(codec, log_token_a_transfer_out_abi, log)

                    liquidity_logs.append(LogMint(event_data))

        return liquidity_logs

class CreatePoolLogEvent(LogEvent):
    def __init__(self):
        pass

    def from_event_data(self, event_data: EventData):
        pass


class PositionManager(Contract):
    """

    NFTPositionManager: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol

    """

    NonfungiblePositionManager_abi = Contract._load_abi(__name__, 'abi/NonfungiblePositionManager.abi')['abi']
    UniswapV3Factory_abi = Contract._load_abi(__name__, 'abi/UniswapV3Factory.abi')['abi']
    UniswapV3Pool_abi = Contract._load_abi(__name__, 'abi/UniswapV3Pool.abi')['abi']

    def __init__(self, web3: Web3, nft_position_manager_address: Address, factory_address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(nft_position_manager_address, Address))
        assert(isinstance(factory_address, Address))

        self.web3: Web3 = web3
        self.nft_position_manager_address = nft_position_manager_address
        self.nft_position_manager_contract = self._get_contract(self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address)

        self.factory_address = factory_address
        self.factory_contract = self._get_contract(self.web3, self.UniswapV3Factory_abi, self.factory_address)

    def approve(self, token: Token):
        assert (isinstance(token, Token))

        erc20_token = ERC20Token(self.web3, token.address)

        approval_function = directly()
        return approval_function(erc20_token, self.nft_position_manager_address, 'NonfungiblePositionManager')

    def create_pool(self, token_a: Token, token_b: Token, fee: int, initial_price: int) -> Transact:
        """ instantiate new pool and initialize pool fee
            Interacts with contract method defined here: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/base/PoolInitializer.sol
        """
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))
        assert (isinstance(fee, int))
        assert (isinstance(initial_price, int))
        
        create_pool_args = [
            token_a.address.address,
            token_b.address.address,
            fee,
            initial_price
        ]

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        "createAndInitializePoolIfNecessary", create_pool_args)

    def decrease_liquidity(self, params: DecreaseLiquidityParams) -> Transact:
        assert(isinstance(params, DecreaseLiquidityParams))

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'decreaseLiquidity', [tuple(params.calldata_args)])

    def get_logs_from_receipt(self, receipt: Receipt, topics: List[HexBytes], event_names: List[str], log_class: LogEvent) -> List:
        """ Retrieve method call return data from log events
            topic can be generated by running on seth CLI:  seth keccak $(seth --from-ascii "{event_name}({method_signature})")
        """
        assert (isinstance(receipt, Receipt))
        assert (isinstance(topics, List))
        assert (isinstance(event_names, str))
        # assert (isinstance(log_class, LogEvent))

        logs = []

        if receipt.logs is not None:
            for log in receipt.logs:
                for topic in topics:
                    if len(log['topics']) > 0 and log['topics'][0] == topic:
                        for event_name in event_names:
                            log_event_abi = [abi for abi in self.NonfungiblePositionManager_abi if abi.get('name') == event_name][0]
                            codec = ABICodec(default_registry)
                            event_data = get_event_data(codec, log_event_abi, log)

                            logs.append(log_class.from_event_data(event_data))

        return logs

    # TODO: determine if this is redundant with just directly instantiating MintParams?
    def generate_mint_params(self, web3: Web3, position: Position, recipient: Address, slippage_tolerance: float, deadline: int = None) -> MintParams:
        """ Returns a MintParams object for use in a mint() call """
        assert (isinstance(web3, Web3))
        assert (isinstance(position, Position))
        assert (isinstance(recipient, Address))
        assert (isinstance(slippage_tolerance, float))
        assert (isinstance(deadline, int) or (deadline is None))

        return MintParams(web3, position, recipient, slippage_tolerance, deadline)

    # TODO: figure out how to build out the Position object
    def mint(self, params: MintParams) -> Transact:
        """ Mint a new position NFT by adding liquidity to the specified tick range """
        assert(isinstance(params, MintParams))

        # get Invocation
        # mint_invocation = params.prepare_invocation()
        # get Transact
        # transact = mint_invocation.invoke()
        # return transact

        # print([params.calldata.as_bytes()], type([params.calldata.as_bytes()]), type(params.calldata.as_bytes()))
        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'mint', [tuple(params.calldata_args)], None, self._get_minted_token_id_result_function)

    # TODO: change return type to UniV3NFT
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

    def get_pool_state(self, pool_contract) -> dict:
        struct = pool_contract.functions.slot0().call()
        print(struct)
        return struct

    def get_pool_ticks(self, pool_contract, current_tick: int) -> List:
        ticks = pool_contract.functions.ticks(current_tick).call()
        return ticks

    def positions(self, token_id: int) -> Position:
        """ Return liquidity and reserve information for a given NFT's token_id """
        assert (isinstance(token_id, int))

        position = self.nft_position_manager_contract.functions.positions(token_id).call()

        # TODO: dynamically retrieve token info from address
        token_0 = Token("DAI", Address(position[2]), 18)
        token_1 = Token("USDC", Address(position[3]), 6)
        fee = position[4]

        pool_address = self.get_pool_address(token_0, token_1, fee)
        pool_contract = self.get_pool_contract(pool_address)
        pool_state = self.get_pool_state(pool_contract)

        # pool_amount_1, pool_amount_0 =
        # sqrt_ratio_x96 = encodeSqrtRatioX96(pool_amount_1, pool_amount_0)
        price_sqrt_ratio_x96 = pool_state[0]
        tick_current = pool_state[1]
        ticks = self.get_pool_ticks(pool_contract, tick_current)

        print("pool ticks", ticks)
        in_range_liquidity = self.sum_liquidity_in_range()

        pool = Pool(token_0, token_1, fee, price_sqrt_ratio_x96, in_range_liquidity, tick_current, ticks)

        tick_lower = position[5]
        tick_upper = position[6]
        liquidity = position[7]

        return Position(pool, tick_lower, tick_upper, liquidity)

    def liquidity_at_price(self, sqrt_price_x96: int) -> int:
        """ Uses equations (L = sqrt(x*y*) and sqrt_price = sqrt(y/x) """

    # TODO: implement: https://github.com/Uniswap/uniswap-v3-periphery/blob/9ca9575d09b0b8d985cc4d9a0f689f7a4470ecb7/contracts/libraries/LiquidityAmounts.sol
    def sum_liquidity_in_range(self, tick_lower, tick_higher) -> int:
        pass

    # TODO: interact with self.positions() to instantiate NFT and calculate price values
    # NFTs are controlled by NonfungiblePositionManager
    def price_position(self, token_id: int) -> Wad:
        """ Return the Wad price of a given token_id """
        assert (isinstance(token_id, int))

        position_to_price = positions(token_id)

    def increase_liquidity(self, params: IncreaseLiquidityParams) -> Transact:
        assert(isinstance(params, IncreaseLiquidityParams))

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'increaseLiquidity', [tuple(params.calldata_args)])

    def collect(self, params: CollectParams) -> Transact:
        """ Collect fees that have accrued to a given position """
        assert (isinstance(params, CollectParams))

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'collect', params.calldata_args)

    def burn(self, params: BurnParams) -> Transact:
        """ Burn NFT by token_id and redeem for underlying tokens """
        assert (isinstance(params, BurnParams))

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'burn', params.calldata_args)

    @staticmethod
    def _get_minted_token_id_result_function(receipt: Receipt):
        assert (isinstance(receipt, Receipt))

        return list(map(lambda log_mint: log_mint, LogMint.from_receipt(receipt)))


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

