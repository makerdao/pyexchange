#!/bin/sh

# start local web3 rpc server for use in dydx unit tests
py-testrpc -p 8889 &

PYTHONPATH=$PYTHONPATH:./lib/pymaker py.test -x --cov=pyexchange --cov-report=term --cov-append tests/
TEST_RESULT=$?

# kill the local server upon completion of tests
pid=$(lsof -i:8889 -t); kill -TERM $pid || kill -KILL $pid

exit $TEST_RESULT