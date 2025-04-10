import time
import requests
import os

API_SERVER = "http://host.docker.internal:8000"  # This allows Docker to talk to the host machine
NODE_ID = os.getenv("NODE_ID", "unknown")

while True:
    try:
        response = requests.post(f"{API_SERVER}/heartbeat/{NODE_ID}")
        print(f"Heartbeat sent for {NODE_ID}: {response.status_code}")
    except Exception as e:
        print(f"Failed to send heartbeat: {e}")
    time.sleep(2)  # Send heartbeat every 5 seconds