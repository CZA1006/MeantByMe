FROM python:3.11-slim

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir .

# `services` is not an installed package (pyproject installs only `meantbyme`
# from src/), so put the repo root on the path for `import services.gateway.app`.
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["uvicorn", "services.gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
