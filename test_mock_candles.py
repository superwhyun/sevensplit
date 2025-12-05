import requests
import time
import sys

def test_mock_candles():
    base_url = "http://localhost:5001"
    
    print(f"Testing Mock Candles Endpoint at {base_url}...")
    
    # 1. Test fetching candles (should trigger proxy to Upbit)
    url = f"{base_url}/v1/candles/minutes/5"
    params = {"market": "KRW-BTC", "count": 5}
    
    try:
        start_time = time.time()
        resp = requests.get(url, params=params, timeout=10)
        duration = time.time() - start_time
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ [PASS] Fetched {len(data)} candles in {duration:.2f}s")
            if len(data) > 0:
                print(f"   Sample: {data[0]}")
        else:
            print(f"❌ [FAIL] Status Code: {resp.status_code}")
            print(f"   Response: {resp.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ [FAIL] Request failed: {e}")
        sys.exit(1)

    # 2. Test Caching (should be faster and not hit Upbit)
    print("\nTesting Cache...")
    try:
        start_time = time.time()
        resp = requests.get(url, params=params, timeout=10)
        duration = time.time() - start_time
        
        if resp.status_code == 200:
            print(f"✅ [PASS] Fetched cached candles in {duration:.2f}s")
        else:
            print(f"❌ [FAIL] Cache fetch failed: {resp.status_code}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ [FAIL] Cache request failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_mock_candles()
