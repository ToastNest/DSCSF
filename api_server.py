from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import time

app = FastAPI()

# Data Structures
nodes = {}  # { "node_id": {"cpu": 4, "available_cpu": 4, "pods": [], "last_heartbeat": time.time()} }
pods = []  # { "pod_id": 1, "cpu_req": 2 }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

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

    # Define resource limits (CPU and Memory)
    cpu_limit = node.cpu  # Number of CPUs allocated
    memory_limit = f"{node.cpu * 512}m"  # Example: 512MB per CPU

    # Start the node container
    container_name = f"node_{node.node_id}"
    try:
        subprocess.run([
            "docker", "run", "-d", "--rm",
            "--name", container_name,
            "--cpus", str(cpu_limit),  # Limit CPU usage
            "--memory", memory_limit,
            "-e", f"NODE_ID={node.node_id}",
            "--network", "host",  # Limit memory usage
            "alpinekube-node"  # Docker image name (must match your built image)
        ], check=True)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Failed to start Docker container")

    # Register node in internal state
    nodes[node.node_id] = {
        "cpu": node.cpu,
        "available_cpu": node.cpu,
        "pods": [],
        "last_heartbeat": time.time(),
        "container_name": container_name
    }
    print(nodes)
    return {"message": f"Node {node.node_id} registered and container started"}
@app.post("/heartbeat/{node_id}")
def heartbeat(node_id: str):
    if node_id not in nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    nodes[node_id]["last_heartbeat"] = time.time()
    return {"message": "Heartbeat received"}

@app.get("/nodes/")
def get_nodes():
    print("Current Nodes:", nodes)  # Debugging print
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

