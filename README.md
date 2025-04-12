Pip Requirements :

pip install fastapi uvicorn requests

First install:
docker build -t alpinekube-node .

In a terminal : \
uvicorn api_server:app --reload

Fedora: 
python -m uvicorn api_server:app --reload

Ubuntu:
python3 -m uvicorn api_server:app --reload

In another new terminal(s):
python node.py node1
python node.py node2
python cli.py

In another new terminal(s): \
python node.py node1 \
python node.py node2 \
python cli.py \

### Addtional Information:
1. CPU Cores that can be allocated to a Node is restricted by number of CPU Cores available to the Docker Engine. \
2. Minimum Duration of Pod is recommended to be set at 45s for succesful reallocation.