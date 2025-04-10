from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import time

app = FastAPI()


nodes = {} 
pods = []  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

class NodeRegister(BaseModel):
    node_id: str
    cpu: int

class PodRequest(BaseModel):
    pod_id: str
    cpu_req: int
    duration: int

@app.post("/register_node/")
def register_node(node: NodeRegister):
    if node.node_id in nodes:
        raise HTTPException(status_code=400, detail="Node already exists")

    cpu_limit = node.cpu  
    memory_limit = f"{node.cpu * 512}m"  

    container_name = f"node_{node.node_id}"

    try:
        result = subprocess.run([
            "docker", "run", "-d", "--rm",
            "--name", container_name,
            "--cpus", str(cpu_limit),
            "--memory", memory_limit,
            "-e", f"NODE_ID={node.node_id}",
            "--network", "host",
            "alpinekube-node"
            ], capture_output=True, text=True)
    except subprocess.CalledProcessError:
        print("Docker error:", result.stderr)
        raise HTTPException(status_code=500, detail="Failed to start Docker container")

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
    print("Current Nodes:", nodes)  
    return nodes

@app.post("/schedule_pod/")
def schedule_pod(pod: PodRequest):
    best_node_id = None
    max_available_cpu = -1

    for node_id, node in nodes.items():
        if node["available_cpu"] >= pod.cpu_req and node["available_cpu"] > max_available_cpu:
            best_node_id = node_id
            max_available_cpu = node["available_cpu"]

    if best_node_id is None:
        raise HTTPException(status_code=400, detail="No available nodes with required resources")

    node = nodes[best_node_id]
    node["available_cpu"] -= pod.cpu_req
    node["pods"].append(pod.pod_id)

    pods.append({
        "pod_id": pod.pod_id,
        "cpu_req": pod.cpu_req,
        "node_id": best_node_id,
        "status": "Running"
    })

    # Start a thread to mark the pod as completed after duration
    def complete_pod_lifecycle():
        time.sleep(pod.duration)
        node["available_cpu"] += pod.cpu_req
        node["pods"].remove(pod.pod_id)
        for p in pods:
            if p["pod_id"] == pod.pod_id:
                p["status"] = "Completed"
        print(f"Pod {pod.pod_id} completed after {pod.duration} seconds.")

    threading.Thread(target=complete_pod_lifecycle, daemon=True).start()

    return {"message": f"Pod {pod.pod_id} scheduled on Node {best_node_id} for {pod.duration} seconds."}

def health_check():
    while True:
        current_time = time.time()
        for node_id, node in list(nodes.items()):
            if current_time - node["last_heartbeat"] > 10:
                if not node.get("unhealthy", False):
                    node["unhealthy"] = True
                    print(f"Node {node_id} marked unhealthy.")
                elif current_time - node["last_heartbeat"] > 30:
                    print(f"Node {node_id} removed due to prolonged failure.")
                    del nodes[node_id]

        time.sleep(5)  

@app.get("/pods/")
def get_pods():
    return pods


threading.Thread(target=health_check, daemon=True).start()