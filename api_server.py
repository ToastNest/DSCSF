from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import time

app = FastAPI()


nodes = {} 
pods = []  

waiting_pods = []

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
            "docker", "run", "-d", 
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

    pod_info = {
        "pod_id": pod.pod_id,
        "cpu_req": pod.cpu_req,
        "node_id": best_node_id,
        "status": "Running",
        "start_time": time.time(),
        "duration": pod.duration
    }

    pods.append(pod_info)

    # Start a thread to simulate pod execution
    def complete_pod_lifecycle():
        time.sleep(pod.duration)

        # Ensure node still exists and pod is still running
        if pod_info["status"] != "Running":
            return

        if best_node_id not in nodes:
            print(f"❌ Pod {pod.pod_id} failed to complete execution. Node {best_node_id} no longer exists. Sending to Waitlist")
            pod_info["status"] = "Terminated from Old Node"
            return

        current_node = nodes[best_node_id]
        current_node["available_cpu"] += pod.cpu_req
        if pod.pod_id in current_node["pods"]:
            current_node["pods"].remove(pod.pod_id)

        pod_info["status"] = "Completed"
        print(f"✅ Pod {pod.pod_id} completed after {pod.duration} seconds.")

    threading.Thread(target=complete_pod_lifecycle, daemon=True).start()

    return {"message": f"Pod {pod.pod_id} scheduled on Node {best_node_id} for {pod.duration} seconds."}


def health_check():
    while True:
        current_time = time.time()
        for node_id, node in list(nodes.items()):
            time_diff = current_time - node["last_heartbeat"]

            if time_diff > 6:
                if not node.get("unhealthy", False):
                    node["unhealthy"] = True
                    print(f"⚠️ Node {node_id} marked as unhealthy. Attempting restart...")

                    container_name = node["container_name"]
                    cpu_limit = node["cpu"]
                    memory_limit = f"{cpu_limit * 512}m"

                    # Attempt to restart the container
                    try:
                        subprocess.run([
                            "docker","start", container_name
                        ],check=True)

                    except subprocess.CalledProcessError:
                        print(f"❌ Failed to restart node {node_id}. Monitoring for permanent failure.")
                    else:
                        node["last_heartbeat"] = time.time()
                        node["unhealthy"] = False
                        print(f"✅ Node {node_id} successfully restarted.")

                elif time_diff > 15:
                    print(f"⛔ Node {node_id} removed after restart failure and prolonged downtime.")
                    failed_pods = node["pods"]
                    del nodes[node_id]

                    for pod_id in failed_pods:
                        pod_info = next((p for p in pods if p["pod_id"] == pod_id), None)
                        if pod_info:
                            reallocated = False
                            for new_node_id, new_node in nodes.items():
                                if new_node["available_cpu"] >= pod_info["cpu_req"]:
                                    new_node["available_cpu"] -= pod_info["cpu_req"]
                                    new_node["pods"].append(pod_id)
                                    pod_info["node_id"] = new_node_id
                                    print(f"🔁 Pod {pod_id} reallocated to Node {new_node_id}")
                                    reallocated = True
                                    break
                            if not reallocated:
                                if nodes:
                                    pod_info["status"] = "Waiting"
                                    waiting_pods.append(pod_info)
                                    print(f"⏳ Pod {pod_id} added to waitlist due to resource limits.")
                                else:
                                    pod_info["status"] = "Terminated"
                                    print("❌ Unable to reallocate pods. No active nodes.")

        process_waiting_pods()
        time.sleep(5)


def process_waiting_pods():
    for pod in waiting_pods[:]:
        for node_id, node in nodes.items():
            if node["available_cpu"] >= pod["cpu_req"]:
                node["available_cpu"] -= pod["cpu_req"]
                node["pods"].append(pod["pod_id"])
                pod["node_id"] = node_id
                pod["status"] = "Running"
                pod["start_time"] = time.time()
                print(f"🔁 Waitlisted pod {pod['pod_id']} assigned to node {node_id}")
                waiting_pods.remove(pod)

                def complete_pod_lifecycle(pod_info):
                    time.sleep(pod_info["duration"])

                    if pod_info["status"] != "Running":
                        return

                    current_node_id = pod_info["node_id"]
                    if current_node_id not in nodes:
                        pod_info["status"] = "Terminated"
                        print(f"❌ Pod {pod_info['pod_id']} cannot complete. Node {current_node_id} no longer exists.")
                        return

                    node_ref = nodes[current_node_id]
                    node_ref["available_cpu"] += pod_info["cpu_req"]
                    if pod_info["pod_id"] in node_ref["pods"]:
                        node_ref["pods"].remove(pod_info["pod_id"])

                    pod_info["status"] = "Completed"
                    print(f"✅ Pod {pod_info['pod_id']} completed after reallocation.")

                threading.Thread(target=complete_pod_lifecycle,args=(pod,),daemon=True).start()

                break  # Only reallocate to one node at a time



@app.get("/pods/")
def get_pods():
    return pods


threading.Thread(target=health_check, daemon=True).start()