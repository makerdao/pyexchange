# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway
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
import logging
import requests

from typing import Optional
from json import JSONDecodeError
from lib.pymaker.pymaker.util import http_response_summary

get_balances = '''
{
  user(id: "0x0000000000c90bc353314b6911180ed7e06019a9") {
    exchangeBalances {
      userAddress

      ethDeposited
      tokensDeposited
      ethWithdrawn
      tokensWithdrawn
      uniTokenBalance
      
      exchange {
        tokenSymbol
      }
      
      ethBought
      ethSold
      tokensBought
      tokensSold
      ethFeesPaid
      tokenFeesPaid
      ethFeesInUSD
      tokenFeesInUSD
    }
  }
}}
'''

get_market_info = '''query ($id: String!) {
      uniswap(id: $id) {
        exchangeCount
        totalVolumeInEth
        totalLiquidityInEth
        totalVolumeUSD
        totalLiquidityUSD
      }
}
'''

# Uses ETH_DAI exchangeAddress
get_trades = '''{
  transactions(
    where: {
      timestamp_gt: 1544832000
      timestamp_lt: 1591308137
      exchangeAddress: "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11"
      user: "0x85c5c26dc2af5546341fc1988b9d178148b4838b"
    }
    first: 10
  ) {
    id
    exchangeAddress
    block
    fee
    timestamp
    
    tokenPurchaseEvents {
      tokenAmount
      tokenFee
      ethAmount
    }
    ethPurchaseEvents {
      ethAmount
      tokenAmount
    }
  }
}'''

get_trades_variables = {
    'user': "our address",
    'current_timestamp': int(time.time())
}

class GraphClient:

    logger = logging.getLogger()

    def __init__(self, graph_url: str, timeout: float = 9.5):
        assert (isinstance(timeout, float))
        assert (isinstance(graph_url, str))

        self.graph_url = graph_url
        self.timeout = timeout

    def mutation_request(self, mutation: str, variables: dict = None):
        assert (isinstance(graph_url, str))
        assert (isinstance(mutation, str))

        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json'}

        json = {'mutation': mutation}
        if variables:
            json['variables'] = variables

        result = self._result(requests.request(method="POST",
                                               url=graph_url,
                                               headers=headers,
                                               json=json,
                                               timeout=self.timeout))

        logging.info(f"Executed mutation and received response: {result}")
        return result['data']

    def query_request(self, query: str, variables: dict = None) -> dict:
        assert (isinstance(graph_url, str))
        assert (isinstance(query, str))

        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json'}

        json = {'query': query}
        if variables:
            json['variables'] = variables

        result = self._result(requests.request(method="POST",
                                               url=graph_url,
                                               headers=headers,
                                               json=json,
                                               timeout=self.timeout))

        logging.info(f"Executed query and received response: {result}")
        return result['data']

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Graph API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except (RuntimeError, JSONDecodeError):
            raise ValueError(f"Graph API invalid JSON response: {http_response_summary(result)}")

        return data


graph_url = 'https://api.thegraph.com/subgraphs/name/graphprotocol/uniswap'
# graph_url = 'http://127.0.0.1:8000/subgraphs/name/davekaj/uniswap'
uniswap_graph = GraphClient(graph_url)
print(uniswap_graph.query_request(get_market_info, {"id": "1"}))
# print(uniswap_graph.query_request(get_trades))
# print(uniswap_graph.query_request( get_balances))
