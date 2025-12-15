FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps and uv (faster resolver than pip)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir uv

# Copy project metadata and source
COPY pyproject.toml ./
COPY src ./src
# Copy agent card and config files
COPY src/tech_lead_crew/agent-card.json ./src/tech_lead_crew/
COPY src/tech_lead_crew/config ./src/tech_lead_crew/config

# Install Python dependencies using uv (much faster resolver)
RUN uv pip install --system --no-cache .

EXPOSE 8080

CMD ["python", "-m", "tech_lead_crew.main"]

