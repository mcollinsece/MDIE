FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for temporary files
RUN mkdir -p /tmp/dicom

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TMP_DIR=/tmp/dicom

# Run the application
CMD ["python3", "dicom_processor.py"]
