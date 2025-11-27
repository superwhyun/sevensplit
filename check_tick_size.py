import requests
import json

def check_orderbook(ticker="KRW-SOL"):
    url = f"https://api.upbit.com/v1/orderbook?markets={ticker}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching orderbook: {response.status_code} {response.text}")
        return

    data = response.json()
    if not data:
        print("No orderbook data found")
        return

    orderbook_units = data[0]['orderbook_units']
    
    print(f"--- Orderbook for {ticker} ---")
    previous_ask = None
    for unit in orderbook_units[:5]:
        ask_price = unit['ask_price']
        bid_price = unit['bid_price']
        
        diff = 0
        if previous_ask:
            diff = ask_price - previous_ask
            
        print(f"Ask: {ask_price} (Diff: {diff}), Bid: {bid_price}")
        previous_ask = ask_price

if __name__ == "__main__":
    check_orderbook()
