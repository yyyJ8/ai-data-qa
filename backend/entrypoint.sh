#!/bin/sh
set -e

# 业务库不存在时建库灌数（幂等，已有数据则跳过）
python -m app.db.init_db

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
