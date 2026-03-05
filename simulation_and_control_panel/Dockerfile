FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    sumo sumo-tools sumo-doc \
    python3 python3-pip curl \
    && rm -rf /var/lib/apt/lists/*
ENV SUMO_HOME=/usr/share/sumo
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python3", "backend/app.py"]
