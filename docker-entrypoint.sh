#!/bin/bash
set -e

echo "Starting RAG Knowledge Base Services..."

# 启动 API Server (包含前端静态文件)
echo "Starting API Server on port 8000..."
python -m src.api_server &
API_PID=$!

# 启动 MCP Server
echo "Starting MCP Server on port 8001..."
python -m src.mcp_server &
MCP_PID=$!

# 等待所有子进程
wait $API_PID $MCP_PID
