FROM e2bdev/desktop:latest

# Node.js 20.x LTS (eliminates ~30s install per sandbox)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Python 3.12 + pip (for Python project support)
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Pre-install common global tools used by web app projects
RUN npm install -g serve http-server vite

# Pre-install common build deps (native modules, canvas, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
