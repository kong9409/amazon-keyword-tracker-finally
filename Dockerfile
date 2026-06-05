FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8766

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py launcher.py lark_writer.py sorftime_adapter.py ./
COPY static ./static

RUN mkdir -p data exports data/jobs

EXPOSE 8766

CMD ["python", "app.py"]
