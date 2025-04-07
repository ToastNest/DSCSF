FROM python:3.9-slim
WORKDIR /DSCSF

COPY heartbeat.py .

RUN pip install requests

CMD ["python", "heartbeat.py"]
