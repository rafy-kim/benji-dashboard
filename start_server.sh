#!/bin/bash
# 대시보드 웹서버 시작 스크립트

cd /Users/benji/clawd/dashboard
PORT=8080

echo "🌐 벤지 대시보드 서버 시작..."
echo "📍 http://192.168.45.47:${PORT}"
echo ""

python3 -m http.server $PORT
