import requests
import time
import sys

API_URL = "http://127.0.0.1:8000"
NODE_ID = sys.argv[1] if len(sys.argv) > 1 else "node1"
CPU = 4  # Simulated CPU cores

# Register the node
requests.post(f"{API_URL}/register_node/", json={"node_id": NODE_ID, "cpu": CPU})

while True:
    try:
        requests.post(f"{API_URL}/heartbeat/{NODE_ID}")
    except Exception:
        print(f"Node {NODE_ID} failed to send heartbeat.")
    time.sleep(5)  # Send heartbeat every 5 seconds
