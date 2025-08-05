# Use a lightweight Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy project files to container
COPY . /app/

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Optional: expose port (used if you run a webserver, otherwise ignored)
EXPOSE 8080

# Run your script (make sure this file exists)
CMD ["python", "server.py"]
