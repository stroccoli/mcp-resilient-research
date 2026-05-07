FROM python:3.11-slim

WORKDIR /app

# Install build deps for any native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata first so pip can resolve deps (better layer caching)
COPY pyproject.toml README.md ./

# Copy source package
COPY resilient_research/ resilient_research/

# Install the project and all dependencies
RUN pip install --no-cache-dir .

EXPOSE 8000

# DATABASE_PATH can be overridden to a mounted volume path at runtime
ENV DATABASE_PATH=/data/research.db

CMD ["resilient-research"]
