FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install google-genai httpx

COPY agent/ /agent/

RUN mkdir -p /comms /output/images /workspace \
    && chmod 777 /comms /output /output/images /workspace

# Set git identity for both root and the default 'user' account
RUN git config --global user.email "agent@devshowcase.app" \
    && git config --global user.name "DevShowcase Agent" \
    && mkdir -p /home/user && cp /root/.gitconfig /home/user/.gitconfig \
    && chown -R 1000:1000 /home/user/.gitconfig
