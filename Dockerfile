# 阶段1: 构建前端
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# 阶段2: Python 后端
FROM python:3.10-slim
WORKDIR /app

# Install system dependencies for FAISS
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config.yaml.example ./config.yaml.example

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist ./static

# Create data directories
RUN mkdir -p /app/faiss_data /app/uploads

# Set working directory
WORKDIR /app

# Expose ports
EXPOSE 18000 18001

# Copy and setup entrypoint script
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Run the server
ENTRYPOINT ["./docker-entrypoint.sh"]
