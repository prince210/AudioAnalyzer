# Use lightweight official Python image
FROM python:3.10-slim

# Prevent Python from writing bytecode and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8020

WORKDIR /app

# Install necessary build tools and packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install CPU PyTorch + Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copy application code
COPY . .

# Ensure output directory exists
RUN mkdir -p final_video_frames/devotional

# Expose port 8020
EXPOSE 8020

# Run uvicorn server
CMD ["uvicorn", "fast_studio_app:app", "--host", "0.0.0.0", "--port", "8020"]
