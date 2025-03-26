# Use a multi-architecture base image
FROM --platform=$BUILDPLATFORM python:3.10-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY application/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --default-timeout=600 -r requirements.txt
# Explicitly install uvicorn
RUN pip install --no-cache-dir uvicorn

# Start a new stage for the final image
FROM --platform=$TARGETPLATFORM python:3.10-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
# Copy the uvicorn executable
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY application/ /app/application/
COPY data/ /app/data/
COPY rule/ /app/rule/
COPY setup_paths.py /app/
COPY web_application/ /app/web_application/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV LLM_EXCEL_BASE_PATH=/app
# Make sure uvicorn is in PATH
ENV PATH="/usr/local/bin:${PATH}"

# Create directories needed by the application
RUN mkdir -p /app/json /app/log /app/sessions /app/output /app/uploads

# Expose the API port
EXPOSE 8000

# Set working directory to web application
WORKDIR /app/web_application

# Command to run the API server - use full path to uvicorn
CMD ["/usr/local/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]