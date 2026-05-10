# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (ffmpeg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of your application
COPY . .

# Create necessary directories
RUN mkdir -p temp_videos temp_thumbs downloads thumbs

# Default command (Railway will override this)
# If you want to run your bot, uncomment the line below:
# CMD ["python3", "bot.py"]

# Or keep it open for Railway to handle:
CMD ["sleep", "infinity"]
