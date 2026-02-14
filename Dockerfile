# Use Python 3.11 slim image
FROM python:3.11-slim

# Install FFmpeg and other dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY bot.py .
COPY sounds.json .
COPY .env .
COPY templates/ templates/
COPY assets/ assets/

# Expose Flask port
EXPOSE 5000

# Create volumes for persistent data
VOLUME ["/app/assets", "/app/sounds.json"]

# Run the bot
CMD ["python", "bot.py"]
