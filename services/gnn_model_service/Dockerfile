FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive 

WORKDIR /app
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

# 1. Install PyTorch FIRST (Explicitly pulling the CPU version)
RUN pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu

# 2. Install PyG linked specifically to that PyTorch version
RUN pip install --no-cache-dir torch-scatter torch-sparse torch-geometric --extra-index-url https://data.pyg.org/whl/torch-2.1.0+cpu.html

# 3. Install the rest of the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]