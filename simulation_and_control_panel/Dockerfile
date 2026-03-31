FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    sumo sumo-tools sumo-doc \
    python3 python3-pip curl \
    && rm -rf /var/lib/apt/lists/*
ENV SUMO_HOME=/usr/share/sumo
WORKDIR /app

# 1. Copy and install simulation panel requirements
COPY simulation_and_control_panel/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# REMOVED: mpc_traffic_control install — MPC runs as its own service container

# 2. Copy the rest of the simulation panel code
COPY simulation_and_control_panel /app

EXPOSE 5000
CMD ["python3", "backend/app.py"]