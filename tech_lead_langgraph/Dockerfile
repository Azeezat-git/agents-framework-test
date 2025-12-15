FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps if needed later; keep minimal for now
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Copy project metadata and source
COPY pyproject.toml ./
COPY src ./src

# Install Python dependencies (from pyproject) after source is present
RUN pip install --no-cache-dir --prefer-binary \
    "urllib3>=1.26.18,<2.2" \
    "idna>=3.6,<3.7" \
    .

EXPOSE 8080

# Entrypoint: starts uvicorn via main.py (uses KAgentApp if available)
CMD ["python", "-m", "tech_lead_langgraph.main"]

