FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # The app imports docling_test.* from src/ without being pip-installed.
    PYTHONPATH=/app/src

WORKDIR /app

# curl is used by the container healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch: the default PyPI wheel pulls ~4.6 GB of CUDA libraries,
# which this 20 GB disk cannot hold. Docling runs inference on CPU anyway.
RUN pip install torch==2.15.0 torchvision==0.29.2 \
    --index-url https://download.pytorch.org/whl/cpu

# Remaining dependencies (pinned to the versions in uv.lock).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application files.
COPY app.py ./
COPY src ./src
COPY data ./data

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
    CMD curl -fsS http://localhost:8501/docling-demo/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.runOnSave=false"]
