### Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p samples static templates utils agents

# Expose port
EXPOSE 8000

# Start Redis and the application
CMD redis-server --daemonize yes && uvicorn main:app --host 0.0.0.0 --port 8000
