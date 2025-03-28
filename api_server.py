from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading
import time

app = FastAPI()

# Data Structures
nodes = {}  # { "node_id": {"cpu": 4, "available_cpu": 4, "pods": [], "last_heartbeat": time.time()} }
pods = []  # { "pod_id": 1, "cpu_req": 2 }

class NodeRegister(BaseModel):
    node_id: str
    cpu: int

class PodRequest(BaseModel):
    pod_id: str
    cpu_req: int

@app.post("/register_node/")
def register_node(node: NodeRegister):
    if node.node_id in nodes:
        raise HTTPException(status_code=400, detail="Node already exists")
    nodes[node.node_id] = {"cpu": node.cpu, "available_cpu": node.cpu, "pods": [], "last_heartbeat": time.time()}
    return {"message": "Node registered successfully"}

@app.post("/heartbeat/{node_id}")
def heartbeat(node_id: str):
    if node_id not in nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    nodes[node_id]["last_heartbeat"] = time.time()
    return {"message": "Heartbeat received"}

@app.get("/nodes/")
def get_nodes():
    return nodes

@app.post("/schedule_pod/")
def schedule_pod(pod: PodRequest):
    for node_id, node in nodes.items():
        if node["available_cpu"] >= pod.cpu_req:
            node["available_cpu"] -= pod.cpu_req
            node["pods"].append(pod.pod_id)
            pods.append({"pod_id": pod.pod_id, "cpu_req": pod.cpu_req, "node_id": node_id})
            return {"message": f"Pod {pod.pod_id} scheduled on Node {node_id}"}
    raise HTTPException(status_code=400, detail="No available nodes with required resources")

def health_check():
    while True:
        current_time = time.time()
        for node_id, node in list(nodes.items()):
            if current_time - node["last_heartbeat"] > 10:  # Node timeout (10s)
                print(f"Node {node_id} is down!")
                del nodes[node_id]
        time.sleep(5)  # Run health check every 5 seconds

# Start health monitor in the background
threading.Thread(target=health_check, daemon=True).start()

