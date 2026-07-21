FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=hosted \
    HOST=0.0.0.0

WORKDIR /app

# CLI 模式由容器内官方 sorftime-cli 执行；网页用户只输入 Account-SK，
# 不接受也不执行用户提供的任意 Shell 命令。
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm ca-certificates \
    && npm install -g sorftime-cli \
    && rm -rf /var/lib/apt/lists/* /root/.npm

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Zeabur 会自动注入 PORT；app.py 读取 $PORT 并监听 0.0.0.0。
CMD ["python", "app.py", "--no-browser"]
