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

from web3 import Web3, HTTPProvider

from pyexchange.idex import IDEXApi, IDEX
from pymaker import Address


web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
idex = IDEX(web3, Address('0x2a0c0dbecc7e4d658f48e01e3fa353f44050c208'))
idex_api = IDEXApi(idex, 'https://api.idex.market', 15.5)

print(idex_api.ticker('DAI_ETH'))
