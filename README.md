# pyexchange

Python API wrappers for some cryptocurrency exchanges.

[![Build Status](https://travis-ci.org/makerdao/pyexchange.svg?branch=master)](https://travis-ci.org/makerdao/pyexchange)
[![codecov](https://codecov.io/gh/makerdao/pyexchange/branch/master/graph/badge.svg)](https://codecov.io/gh/makerdao/pyexchange)

<https://chat.makerdao.com/channel/keeper>


## Key facts

* These API wrappers expose only those endpoints which were necessary to implement
  `market-maker-keeper` (<https://github.com/makerdao/market-maker-keeper>), `market-maker-stats`
  (<https://github.com/makerdao/market-maker-stats>) and `sync-trades` (<https://github.com/makerdao/sync-trades>).
  Due to it they cover most only order placement, order cancellation, reading balances and open orders,
  and retrieving past trade history.

* This library uses temporary file storage for past trades in order do avoid querying the server over and over again
  (in the case of Bibox) and in order to be able to still show old trades which have already disappeared from the
  API results (in the case of gate.io). Data is held in files, read and saved with _TinyDB_
  (<http://tinydb.readthedocs.io/en/latest/>) and kept in a cache directory in an os-specific location thanks
  to _appdirs_ (<https://pypi.python.org/pypi/appdirs>).

* This library depends on `pymaker` because IDEX integration involves interacting with its smart contract.
  In addition to that, other exchange APIs use the `Wad` class which is defined `pymaker`.

* There is almost no test coverage as of today. The exception is some part of the IDEX API.


## License

See [COPYING](https://github.com/makerdao/pyexchange/blob/master/COPYING) file.
