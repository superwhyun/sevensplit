import uvicorn
import multiprocessing
import os
import time
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_mock_server():
    print("Starting Mock Server on port 5001...")
    uvicorn.run("mock_api_server:app", host="0.0.0.0", port=5001, log_level="info", reload=True)

def run_main_server():
    print("Starting Main Bot Server on port 8000...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info", reload=True)

if __name__ == "__main__":
    # Check if we need to run mock server
    server_url = os.getenv("UPBIT_OPEN_API_SERVER_URL", "")
    run_mock = "5001" in server_url or "localhost" in server_url or "127.0.0.1" in server_url
    
    # Or explicitly check a flag? 
    # User said: "mock mode에서 real mode로 전환할때 api 키와 서버 주소만 바꾸면 바로 할 수 있게 해야하니까"
    # So if the URL is set to localhost:5001, we should probably auto-start the mock server.
    
    processes = []

    if run_mock:
        p_mock = multiprocessing.Process(target=run_mock_server)
        p_mock.start()
        processes.append(p_mock)
        # Give mock server a moment to start
        time.sleep(1)
    else:
        print(f"Mock server not started (Server URL: {server_url})")

    p_main = multiprocessing.Process(target=run_main_server)
    p_main.start()
    processes.append(p_main)

    try:
        # Wait for processes
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nStopping servers...")
        for p in processes:
            p.terminate()
            p.join()
