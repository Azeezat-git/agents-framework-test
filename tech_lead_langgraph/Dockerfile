FROM python:3.13-slim


WORKDIR /app

# Install system deps if needed later; keep minimal for now
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY src ./src
COPY agent-card.json ./agent-card.json



EXPOSE 8080

# Entrypoint: starts uvicorn via main.py 
CMD ["python", "-m", "tech_lead_langgraph.main"]

