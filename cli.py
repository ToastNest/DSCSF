import requests

API_URL = "http://127.0.0.1:8000"

def main():
    while True:
        print("\n1. Register Node")
        print("2. View Nodes")
        print("3. Schedule Pod")
        print("4. Exit")
        choice = input("Enter choice: ")

        if choice == "1":
            node_id = input("Enter node ID: ")
            cpu = int(input("Enter CPU cores: "))
            res = requests.post(f"{API_URL}/register_node/", json={"node_id": node_id, "cpu": cpu})
            print(res.json())

        elif choice == "2":
            res = requests.get(f"{API_URL}/nodes/")
            print(res.json())

        elif choice == "3":
            pod_id = input("Enter pod ID: ")
            cpu_req = int(input("Enter required CPU: "))
            res = requests.post(f"{API_URL}/schedule_pod/", json={"pod_id": pod_id, "cpu_req": cpu_req})
            print(res.json())

        elif choice == "4":
            break

        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()
