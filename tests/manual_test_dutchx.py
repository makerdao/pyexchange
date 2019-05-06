# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 grandizzy
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

from pyexchange.dutchx import DutchXApi
from pymaker import Wad, Address

dutchx = DutchXApi("https://dutchx.d.exchange/api", 9.5)
print(dutchx.get_balance(Address('0x0000'), Address('0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2')))



