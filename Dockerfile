FROM python:3.11-slim

WORKDIR /app

# 設置環境變量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 安裝系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 複製項目文件
COPY . /app/

# 安裝Python依賴
RUN pip install --no-cache-dir -r requirements.txt

# 創建日誌目錄
RUN mkdir -p /app/logs

# 暴露端口
EXPOSE 8000

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

# 啟動命令
CMD ["python", "run_server.py"]
