import logging
import sys
import time
from pprint import pprint

from pyexchange.erisx import ErisxApi

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(threadName)-18s %(message)s', level=logging.DEBUG)
client = ErisxApi(fix_trading_endpoint=sys.argv[1], fix_trading_user=sys.argv[2],
                  fix_marketdata_endpoint=sys.argv[3], fix_marketdata_user=sys.argv[4],
                  password=sys.argv[5],
                  clearing_url="https://clearing.newrelease.erisx.com/api/v1/",
                  api_key=sys.argv[6], api_secret=sys.argv[7], account_id=0)
# print(sys.argv)
print("ErisxApi created\n")
# print(client.get_balances())
# time.sleep(30)

securities = client.get_markets()
print(f"Received {len(securities)} securities:")
pprint(securities)
time.sleep(2)

pair = client.get_pair("ETH/USD")
pprint(pair)
time.sleep(1)

new_order = client.place_order('ETH/USD', False, 185.1, 0.2)
print(f"Placed new order: {new_order}")
time.sleep(1)

orders = client.get_orders("ETH/USD")
print(f"Received {len(orders)} orders:")
pprint(orders)
time.sleep(3)

trades = client.get_trades("ETH/USD")
print(f"Received {len(list(trades))} trades:")
pprint(trades)
time.sleep(1)

# order_id = {
#     'client': 'c697ab94-88fb-4f54-a441-6ec0e335d8d0',
#     'erisx': '281474978087464'
# }
# cancel_order = client.cancel_order(order_id, "ETH/USD", False)
# print(f"Cancelling order: {order_id}")
# pprint(cancel_order)
# time.sleep(10)

print("Disconnecting")
del client
time.sleep(3)

