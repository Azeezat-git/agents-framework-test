FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

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

CMD ["python", "-m", "tech_lead_crew.main"]

