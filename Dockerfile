FROM python:3.11-slim

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir .

# `services` is not an installed package (pyproject installs only `meantbyme`
# from src/), so put the repo root on the path for `import services.gateway.app`.
ENV PYTHONPATH=/app

EXPOSE 8080

# Bind to the platform-injected $PORT (Zeabur routes the public domain to it);
# fall back to 8080 for plain `docker run`. Shell form so ${PORT} expands.
CMD ["sh", "-c", "uvicorn services.gateway.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
