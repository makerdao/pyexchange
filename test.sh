#!/bin/sh

# start local web3 rpc server for use in dydx unit tests
py-testrpc -p 8889 &

# Pull the docker image
docker pull makerdao/testchain-pymaker:unit-testing

# Remove existing container if tests not gracefully stopped
docker-compose down

# Start ganache
docker-compose up -d ganache

# Start parity and wait to initialize
docker-compose up -d parity
sleep 2

PYTHONPATH=$PYTHONPATH:./lib/pymaker py.test -x --cov=pyexchange --cov-report=term --cov-append tests/test_uniswapv2.py
TEST_RESULT=$?

# Cleanup local parity node
docker-compose down

# kill the local server upon completion of tests
pid=$(lsof -i:8889 -t); kill -TERM $pid || kill -KILL $pid

exit $TEST_RESULT