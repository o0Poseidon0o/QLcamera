#!/bin/bash
set -e

echo "=================================================="
echo "🚀 ĐANG KÉO MÃ NGUỒN MỚI TỪ GITHUB..."
echo "=================================================="
git pull

echo ""
echo "=================================================="
echo "📦 ĐANG BUILD VÀ CẬP NHẬT CONTAINER DOCKER..."
echo "=================================================="
docker compose up -d --build

echo ""
echo "=================================================="
echo "✅ HỆ THỐNG ĐÃ CẬP NHẬT THÀNH CÔNG!"
echo "=================================================="
docker compose ps
