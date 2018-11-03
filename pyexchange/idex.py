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

import logging
from pprint import pformat
from typing import List

import requests
from web3 import Web3

from pymaker import Contract, Address, Transact, Wad
from pymaker.sign import eth_sign, to_vrs
from pymaker.tightly_packed import encode_address, encode_uint256, encode_bytes
from pymaker.token import ERC20Token
from pymaker.util import bytes_to_hexstring, hexstring_to_bytes, http_response_summary


class Order:
    def __init__(self,
                 order_id: int,
                 order_hash: str,
                 nonce: int,
                 timestamp: int,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 money: Wad):

        assert(isinstance(order_id, int))
        assert(isinstance(order_hash, str))
        assert(isinstance(nonce, int))
        assert(isinstance(timestamp, int))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(money, Wad))

        self.order_id = order_id
        self.order_hash = order_hash
        self.nonce = nonce
        self.timestamp = timestamp
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.money = money

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount

    def __repr__(self):
        return pformat(vars(self))


class IDEX(Contract):
    """A client for the IDEX Exchange contract.

    You can find the source code of the IDEX Exchange contract here:
    <https://etherscan.io/address/0x2a0c0dbecc7e4d658f48e01e3fa353f44050c208#code>.

    Some API docs can be found here:
    <https://github.com/AuroraDAO/idex-api-docs>.

    Attributes:
        web3: An instance of `Web` from `web3.py`.
        address: Ethereum address of the IDEX Exchange contract.
    """

    abi = Contract._load_abi(__name__, 'abi/IDEX.abi')
    bin = Contract._load_bin(__name__, 'abi/IDEX.bin')

    ETH_TOKEN = Address("0x0000000000000000000000000000000000000000")

    @staticmethod
    def deploy(web3: Web3, fee_account: Address):
        """Deploy a new instance of the IDEX Exchange contract.

        Args:
            web3: An instance of `Web` from `web3.py`.
            fee_account: The address of the account which will collect fees.

        Returns:
            An `IDEX` class instance.
        """
        return IDEX(web3=web3, address=Contract._deploy(web3, IDEX.abi, IDEX.bin, [fee_account.address]))

    def __init__(self, web3: Web3, address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(address, Address))

        self.web3 = web3
        self.address = address
        self._contract = self._get_contract(web3, self.abi, address)

    def fee_account(self) -> Address:
        """Returns the address of the fee account i.e. the account that receives all fees collected.

        Returns:
            The address of the fee account.
        """
        return Address(self._contract.call().feeAccount())

    def approve(self, tokens: List[ERC20Token], approval_function):
        """Approve the IDEX Exchange contract to fully access balances of specified tokens.

        For available approval functions (i.e. approval modes) see `directly` and `via_tx_manager`
        in `pymaker.approval`.

        Args:
            tokens: List of :py:class:`pymaker.token.ERC20Token` class instances.
            approval_function: Approval function (i.e. approval mode).
        """
        assert(isinstance(tokens, list))
        assert(callable(approval_function))

        for token in tokens:
            approval_function(token, self.address, 'IDEX Exchange contract')

    def deposit(self, amount: Wad) -> Transact:
        """Deposits `amount` of raw ETH to IDEX.

        Args:
            amount: Amount of raw ETH to be deposited on IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'deposit', [], {'value': amount.value})

    def withdraw(self, amount: Wad) -> Transact:
        """Withdraws `amount` of raw ETH from IDEX.

        The withdrawn ETH will get transferred to the calling account.

        Args:
            amount: Amount of raw ETH to be withdrawn from IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'withdraw',
                        [self.ETH_TOKEN.address, amount.value])

    def balance_of(self, user: Address) -> Wad:
        """Returns the amount of raw ETH deposited by the specified user.

        Args:
            user: Address of the user to check the balance of.

        Returns:
            The raw ETH balance kept in the IDEX Exchange contract by the specified user.
        """
        assert(isinstance(user, Address))
        return Wad(self._contract.call().balanceOf(self.ETH_TOKEN.address, user.address))

    def deposit_token(self, token: Address, amount: Wad) -> Transact:
        """Deposits `amount` of ERC20 token `token` to IDEX.

        Tokens will be pulled from the calling account, so the IDEX contract needs
        to have appropriate allowance. Either call `approve()` or set the allowance manually
        before trying to deposit tokens.

        Args:
            token: Address of the ERC20 token to be deposited.
            amount: Amount of token `token` to be deposited to IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(token, Address))
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'depositToken',
                        [token.address, amount.value])

    def withdraw_token(self, token: Address, amount: Wad) -> Transact:
        """Withdraws `amount` of ERC20 token `token` from IDEX.

        Tokens will get transferred to the calling account.

        Args:
            token: Address of the ERC20 token to be withdrawn.
            amount: Amount of token `token` to be withdrawn from IDEX.

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(token, Address))
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'withdraw',
                        [token.address, amount.value])

    def balance_of_token(self, token: Address, user: Address) -> Wad:
        """Returns the amount of ERC20 token `token` deposited by the specified user.

        Args:
            token: Address of the ERC20 token return the balance of.
            user: Address of the user to check the balance of.

        Returns:
            The ERC20 token `token` balance kept in the IDEX contract by the specified user.
        """
        assert(isinstance(token, Address))
        assert(isinstance(user, Address))
        return Wad(self._contract.call().balanceOf(token.address, user.address))

    def __repr__(self):
        return f"IDEX('{self.address}')"


class IDEXApi:
    """A client for the IDEX API.

    <https://github.com/AuroraDAO/idex-api-docs>

    Attributes:
        idex: The IDEX Exchange contract.
    """
    logger = logging.getLogger()
    timeout = 15.5

    def __init__(self, idex: IDEX, api_server: str, timeout: float):
        assert(isinstance(idex, IDEX))
        assert(isinstance(api_server, str))
        assert(isinstance(timeout, float))

        self.idex = idex
        self.api_server = api_server
        self.timeout = timeout

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_post("/returnTicker", {'market': pair})

    def next_nonce(self) -> int:
        return int(self._http_post("/returnNextNonce", {'address': self._our_address()})['nonce'])

    def get_balances(self):
        return self._http_post("/returnCompleteBalances", {'address': self._our_address()})

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))

        result = self._http_post("/returnOpenOrders", {'market': pair, 'address': self._our_address()})
        return list(map(self._json_to_order, result))

    def place_order(self,
                    pay_token: Address,
                    pay_amount: Wad,
                    buy_token: Address,
                    buy_amount: Wad) -> Order:
        """Places a new order.

        Args:
            pay_token: Address of the ERC20 token you want to put on sale.
            pay_amount: Amount of the `pay_token` token you want to put on sale.
            buy_token: Address of the ERC20 token you want to be paid with.
            buy_amount: Amount of the `buy_token` you want to receive.

        Returns:
            New order as an instance of the :py:class:`pyexchange.idex.Order` class.
        """
        assert(isinstance(pay_token, Address))
        assert(isinstance(pay_amount, Wad))
        assert(isinstance(buy_token, Address))
        assert(isinstance(buy_amount, Wad))

        expires = 0
        nonce = self.next_nonce()
        order_hash = keccak_256(encode_address(self.idex.address) +
                                encode_address(buy_token) +
                                encode_uint256(buy_amount.value) +
                                encode_address(pay_token) +
                                encode_uint256(pay_amount.value) +
                                encode_uint256(expires) +
                                encode_uint256(nonce) +
                                encode_address(Address(self._our_address()))).digest()

        signature = eth_sign(order_hash, self.idex.web3)
        v, r, s = to_vrs(signature)

        data = {
            'tokenBuy': buy_token.address,
            'amountBuy': str(buy_amount.value),
            'tokenSell': pay_token.address,
            'amountSell': str(pay_amount.value),
            'address': self._our_address(),
            'nonce': str(nonce),
            'expires': expires,
            'v': v,
            'r': bytes_to_hexstring(r),
            's': bytes_to_hexstring(s)
        }

        self.logger.info(f"Placing order selling {pay_amount} {pay_token} for {buy_amount} {buy_token}...")

        result = self._http_post("/order", data)
        order = self._json_to_order(result)

        self.logger.info(f"Placed order selling {pay_amount} {pay_token} for {buy_amount} {buy_token} as #{order.order_id}")

        return order

    def cancel_order(self, order: Order) -> bool:
        assert(isinstance(order, Order))

        nonce = self.next_nonce()
        signed_data = keccak_256(encode_bytes(hexstring_to_bytes(order.order_hash)) +
                                 encode_uint256(nonce)).digest()

        signature = eth_sign(signed_data, self.idex.web3)
        v, r, s = to_vrs(signature)

        data = {
            'orderHash': order.order_hash,
            'nonce': str(nonce),
            'address': self._our_address(),
            'v': v,
            'r': bytes_to_hexstring(r),
            's': bytes_to_hexstring(s)
        }

        self.logger.info(f"Cancelling order #{order.order_id}...")

        result = self._http_post("/cancel", data)
        success = result['success'] == 1

        if success:
            self.logger.info(f"Cancelled order #{order.order_id}")
        else:
            self.logger.info(f"Failed to cancel order #{order.order_id}")

        return success

    def _our_address(self) -> str:
        return self.idex.web3.eth.defaultAccount.lower()

    @staticmethod
    def _json_to_order(data: dict) -> Order:
        assert(isinstance(data, dict))

        return Order(order_id=data['orderNumber'],
                     order_hash=data['orderHash'],
                     nonce=data['params']['nonce'],
                     timestamp=data['timestamp'],
                     is_sell=data['type'] == 'sell',
                     price=Wad.from_number(data['price']),
                     amount=Wad.from_number(data['amount']),
                     money=Wad.from_number(data['total']))

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"IDEX API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"IDEX API invalid JSON response: {http_response_summary(result)}")

        if 'error' in data:
            raise Exception(f"IDEX API negative response: {http_response_summary(result)}")

        return data

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                          json=params,
                                          timeout=self.timeout))

    def __repr__(self):
        return f"IDEXApi()"
