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

from pyexchange.uniswapv3_entities import Params, Pool, Position
from pymaker import Calldata, Contract, Address, Transact, Wad
from pymaker.approval import directly
from pymaker.model import Token
from pymaker.token import ERC20Token, NFT


# TODO: figure out division of responsibiliies between uniswapv3_entitites.Pool and UniswapV3
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

    def check_global_state(self):
        """ Retrieve global state varialbe"""
        pass

    def _deadline(self) -> int:
        """Get a predefined deadline."""
        return int(time.time()) + 1000


# TODO: add registering keys directly to SwapRouter?
class SwapRouter:
    """ Class to handle any interactions with UniswapV3 SwapRouter
    
    Code for SwapRouter.sol: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/SwapRouter.sol
    """

    # Iswap_router_abi = Contract._load_abi(__name__, 'abi/ISwapRouter.abi')['abi']

    def __init__(self, uniswap_pool: UniswapV3, swap_router_address: Address) -> None:
        assert(isinstance(uniswap_pool, UniswapV3))
        assert(isinstance(swap_router_address, Address))

        self.uniswap_pool = uniswap_pool

        self.swap_router_address = swap_router_address
        self.swap_router_contract = self._get_contract(self.uniswap_pool.web3, self.Iswap_router_abi, self.swap_router_address)

    def swap_exact_output(self) -> Transact:

        # TODO: generate param Calldata 
        swap_exact_output_args = []

        return Transact(self, self.web3, self.Iswap_router_abi, self.swap_router_address, self.swap_router_contract,
                        "exactOutput", swap_exact_output_args)

    def swap_exact_output_single(self) -> Transact:
        pass

    def swap_exact_input(self) -> Transact:
        """ Given an exact set of inputs, execute swap to target outputs """
        pass

    def swap_exact_input_single(self) -> Transact:
        """ Given an exact input, execute a swap to target output """
        pass


class PositionManager:
    """

    NFTPositionManager: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol

    """

    NonfungiblePositionManager_abi = Contract._load_abi(__name__, 'abi/NonfungiblePositionManager.abi')['abi']


    # TODO: construct callback to be passed to mint()
    ## https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/nonfungiblePositionManager.ts#L162
    ## https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/nonfungiblePositionManager.ts#L44    
    class MintParams(Params):

        # https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/nonfungiblePositionManager.test.ts
        def __init__(self, position: Position, recipient: str, slippage_tolerance: float, deadline: int):
            assert(isinstance(position, Position))
            assert(isinstance(recipient, str))
            assert(isinstance(slippage_tolerance, float))
            assert(isinstance(deadline, int))

            self.position = position
            self.recipient = recipient
            self.slippage_tolerance = slippage_tolerance
            self.deadline = deadline

            calldata_args = [self.position, self.receipt, self.slippage_tolerance, self.deadline]

            # TODO: figure out how to handle struct typing
            method = "mint(struct INonfungiblePositionManager.MintParams, params)"
            # TODO: add fn signature types
            # TODO: figure out how to pass through web3
            self.encode_calldata = self.encode_calldata(web3, method, calldata_args)

        @staticmethod
        def calculate_mint_amounts(self, slippage: int) -> dict:
            assert(isinstance(slippage, int))

            amount0Desired = Wad.from_number(0)

            return {
                "amount0Desired": amount0Desired
            }


    class CollectParams(Params):

        # TODO: pass through the contract, and uniswap_pool
        def __init__(self, uniswap_pool: Pool, recipient: Address, tick_lower: int, tick_upper: int, amounts: dict) -> None:
            assert(isinstance(uniswap_pool, Pool))

            self.params = {}

            self.params.amount1Min = amounts["amount1Min"]
            self.deadline = self._deadline()


    def __init__(self, web3: Web3, nft_position_manager_address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(nft_position_manager_address, Address))

        self.web3: Web3 = web3
        self.nft_position_manager_address = nft_position_manager_address
        self.nft_position_manager_contract = self._get_contract(self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address)

    def approve(self, Token):
        assert (isinstance(token, Token))

        erc20_token = ERC20Token(self.web3, token.address)

        approval_function = directly()
        return approval_function(erc20_token, self.nft_position_manager_address, 'NonfungiblePositionManager')

    def create_pool(self, token_a: Token, token_b: Token, fee: Wad, initial_price: Wad) -> Transact:
        """ instantiate new pool and initialize pool fee """
        assert (isinstance(token_a, Token))
        assert (isinstance(token_b, Token))
        assert (isinstance(fee, Wad))
        assert (isinstance(initial_price, Wad))
        
        create_pool_args = [
            token_a.address.address,
            token_b.address.address,
            fee.value,
            initial_price.value
        ]

        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        "createAndInitializePoolIfNecessary", create_pool_args)

    # TODO: determine how to pass through args
    def generate_mint_params(self, position: Position, recipient: str, slippage_tolerance: float, deadline: int) -> MintParams:
        """ Returns a MintParams object for use in a mint() call """
        assert(isinstance(position, Position))
        assert(isinstance(recipient, str))
        assert(isinstance(slippage_tolerance, float))
        assert(isinstance(deadline, int))

        pool = Pool()
        position = Position()

        return MintParams(position, recipient, slippage_tolerance, deadline)

    # TODO: figure out how to build out the Position object
    def mint(self, params: MintParams) -> Transact:
        """ Mint a new position NFT by adding liquidity to the specified tick range """
        assert(isinstance(params, MintParams))

        # get Invocation
        mint_invocation = params.prepare_invocation()

        # get Transact
        transact = mint_invocation.invoke()
        return transact
        # return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
        #                 'mint', mint_args)

    # TODO: change return type to UniV3NFT
    def migrate_position(self, lp_token_address: Address) -> NFT:
        """ migrate UniV2LP tokens to a v3 NFT """
        assert (isinstance(lp_token_address, Address))

    # TODO: determine if this should return an NFT
    ## use Position instead of NFT?
    def positions(self, token_id: int) -> Position:
        """ """
        assert (isinstance(token_id, int))

        position = self.nft_position_manager_contract.functions.positions(token_id).call()

        return Position(position)

    # TODO: interact with self.positions() to instantiate NFT and calculate price values
    # NFTs are controlled by NonfungiblePositionManager
    def price_position(self, token_id: int) -> Wad:
        """ Return the Wad price of a given token_id """
        assert (isinstance(token_id, int))

    def increase_liquidity(self) -> Transact:
        pass

    def decrease_liquidity(self) -> Transact:
        pass

    def collect(self, collect_params: CollectParams) -> Transact:
        """ Collect fees that have accrued to a given position """
        pass

    def burn(self, token_id: int) -> Transact:
        """ Burn NFT and redeem for underlying tokens """
        assert (isinstance(token_id, int))

        burn_args = [
            token_id
        ]
        return Transact(self, self.web3, self.NonfungiblePositionManager_abi, self.nft_position_manager_address, self.nft_position_manager_contract,
                        'burn', burn_args)




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

