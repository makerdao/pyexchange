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

import requests

from typing import Optional
from json import JSONDecodeError
from lib.pymaker.pymaker.util import http_response_summary

get_balances = '''
{
  user(id: "0x0000000000c90bc353314b6911180ed7e06019a9") {
    exchangeBalances {
      userAddress
      exchangeAddress

      ethDeposited
      tokensDeposited
      ethWithdrawn
      tokensWithdrawn
      uniTokensMinted
      uniTokensBurned

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
}
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

get_trades = '''
{
  transactions(
    where: {
      timeStamp_gt: 1544832000
      timeStamp_lt: 1545696000
      tokenSymbol: "DAI"
      userAddress: "0x85c5c26dc2af5546341fc1988b9d178148b4838b"
    }
    first: 10
  ) {
    id
    exchangeAddress
    userAddress
    block
    ethAmount
    tokenAmount
    fee
    event
    timeStamp
  }
}
'''

class GraphClient:

    def __init__(self, timeout: float = 9.5):
        assert (isinstance(timeout, float))

        self.timeout = timeout

    def graph_request(self, graph_url: str, query: str, variables: dict = None) -> dict:
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
        print(result)
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
uniswap_graph = GraphClient()
# print(uniswap_graph.graph_request(graph_url, get_market_info, {"id": "1"}))
print(uniswap_graph.graph_request(graph_url, get_trades))


