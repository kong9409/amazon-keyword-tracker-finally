FROM node:24-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8766
ENV SF_CLI_PATH=sorftime
ENV SORFTIME_CLI_PROFILE=codex

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && npm install -g sorftime-cli \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python3 -m pip install --break-system-packages --no-cache-dir -r requirements.txt

COPY app.py launcher.py lark_writer.py sorftime_adapter.py ./
COPY static ./static

RUN mkdir -p data exports

EXPOSE 8766

CMD ["python3", "app.py"]
