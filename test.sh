#!/bin/sh

# Remove existing container if tests not gracefully stopped
docker-compose down

# Start ganache
docker-compose up -d ganache

# Wait to initialize
sleep 2

PYTHONPATH=$PYTHONPATH:./lib/pymaker py.test -x --cov=pyexchange --cov-report=term --cov-append tests/
TEST_RESULT=$?

# Cleanup local parity node
docker-compose down

exit $TEST_RESULT