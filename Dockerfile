FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm openjdk-21-jre php-cli bash && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 10001 appuser && mkdir -p /var/data/uploads /var/data/logs && chown -R appuser:appuser /app /var/data
USER appuser
EXPOSE 10000
CMD ["gunicorn","--bind","0.0.0.0:10000","--workers","1","--threads","8","--timeout","0","app:app"]
