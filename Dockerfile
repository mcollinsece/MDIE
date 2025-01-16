FROM python:3.12-alpine


# Install system dependencies
RUN apk add --no-cache imagemagick

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

ENTRYPOINT ["/usr/local/bin/python3"]
# Run the application
CMD ["dicom_processor.py"]
