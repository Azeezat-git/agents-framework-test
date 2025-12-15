FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (from pyproject)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code and configs
COPY src ./src
COPY README.md ./README.md

EXPOSE 8080

CMD ["python", "-m", "tech_lead_crew.main"]

