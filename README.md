Pip Requirements :

pip install fastapi uvicorn requests

First install:
docker build -t alpinekube-node .

In a terminal :
uvicorn api_server:app --reload

Fedora: 
python -m uvicorn api_server:app --reload

In another new terminal(s):
python node.py node1
python node.py node2
python cli.py

