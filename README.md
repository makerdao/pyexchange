# pyexchange

Python API wrappers for some cryptocurrency exchanges.

[![Build Status](https://travis-ci.org/makerdao/pyexchange.svg?branch=master)](https://travis-ci.org/makerdao/pyexchange)
[![codecov](https://codecov.io/gh/makerdao/pyexchange/branch/master/graph/badge.svg)](https://codecov.io/gh/makerdao/pyexchange)

<https://chat.makerdao.com/channel/keeper>


## Key facts

* These API wrappers expose only those endpoints which were necessary to implement
  `market-maker-keeper` (<https://github.com/makerdao/market-maker-keeper>), `market-maker-stats`
  (<https://github.com/makerdao/market-maker-stats>) and `sync-trades`.
  Due to it they cover most only order placement, order cancellation, reading balances and open orders,
  and retrieving past trade history.

* This library depends on `pymaker` because IDEX integration involves interacting with its smart contract.
  In addition to that, other exchange APIs use the `Wad` class which is defined `pymaker`.

* There is almost no test coverage as of today. The exception is some part of the IDEX API.

* If you are looking for more supported exchanges and/or more features, a please have a look
  at `ccxt` (<https://github.com/ccxt/ccxt>). It's a JavaScript / Python / PHP library which
  supports huge number of venues and also has more features than `pyexchange`.


## License

See [COPYING](https://github.com/makerdao/pyexchange/blob/master/COPYING) file.
