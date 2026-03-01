FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install google-genai httpx

COPY agent/ /agent/

RUN mkdir -p /comms /output/images /workspace
