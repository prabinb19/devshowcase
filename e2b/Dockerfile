FROM e2bdev/desktop:latest

# Node.js 20.x LTS (eliminates ~30s install per sandbox)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Python 3.12 + pip (base image is Ubuntu 22.04, needs deadsnakes PPA)
RUN apt-get update && apt-get install -y software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Pre-install common global tools used by web app projects
RUN npm install -g serve http-server vite

# Pre-install common build deps (native modules, canvas, etc.)
# Also install xterm for a visible terminal on the desktop
RUN apt-get update && apt-get install -y \
    build-essential xterm \
    && rm -rf /var/lib/apt/lists/*

# Agent dependencies
RUN pip3 install google-genai httpx

# Bake agent code into the image
COPY agent/ /agent/

# Create directories the agent expects
RUN mkdir -p /comms /output/images /workspace

# Git identity for portfolio commits
RUN git config --global user.name "DevShowcase Agent" \
    && git config --global user.email "agent@devshowcase.app"
