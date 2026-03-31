FROM python:3.11-slim

# Prevent Python from writing pyc files and keep stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
# Add --default-timeout=1000 to prevent the broken pipe
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Copy the worker code
COPY . .

# Run the worker
CMD ["python", "worker.py"]