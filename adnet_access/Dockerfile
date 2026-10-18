ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

WORKDIR /opt/adnet_access
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY app/ ./

ENV PYTHONUNBUFFERED=1
CMD ["python3", "-m", "access.main"]
