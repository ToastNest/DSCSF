FROM python:3.9-slim
WORKDIR /app

COPY heartbeat.py .

RUN pip install requests

CMD ["python", "heartbeat.py"]
