FROM python:3.11-slim

# Install ffmpeg and curl for deno installation
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (required for yt-dlp YouTube challenges)
RUN curl -fsSL https://deno.land/x/install/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

WORKDIR /app

# Install python dependencies from both regular and dev requirements (for FastAPI/uvicorn)
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY . .

# Create downloads folder
RUN mkdir -p downloads

EXPOSE 8000

# Run using the dev.py application entry point
CMD ["python", "dev.py"]
