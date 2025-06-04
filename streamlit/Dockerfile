# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JWT_SECRET= \
    ENCRYPTION_KEY=

# Create a non-root user
RUN useradd -m -s /bin/bash appuser

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create directories for data and backups
RUN mkdir -p /app/data /app/backups \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Make port 8000 available
EXPOSE 8000

# Run the application with secure settings
CMD ["streamlit", "run", "app.py", \
     "--server.port=8000", \
     "--server.address=0.0.0.0", \
     "--server.maxUploadSize=5", \
     "--server.maxMessageSize=5", \
     "--server.enableXsrfProtection=true", \
     "--server.enableCORS=false"]
