# Use UV python for the base image
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Receive the version from GitHub Actions
ARG VERSION

# Set it as an ENV so it's available at runtime
ENV VERSION=$VERSION

# Install curl and clean up apt cache to keep the image slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Run uv to build the application dependencies
WORKDIR /app
COPY . .
RUN uv sync --frozen

# Run
CMD ["uv", "run", "python", "main.py"]
