# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install system dependencies required for geospatial libraries
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libspatialindex-dev \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY create_map_poster.py .
COPY font_management.py .
COPY osm_cache.py .
COPY overpass_servers.py .
COPY plotter_svg.py .
COPY poster_edits.py .
COPY web_app.py .
COPY web/ web/
COPY themes/ themes/
COPY fonts/ fonts/

# Create directories for output and caches
RUN mkdir -p posters cache fonts/cache

# Entrypoint: web interface by default, CLI when given --options
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && chmod +x /usr/local/bin/docker-entrypoint.sh

# Web interface
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/themes', timeout=4)"

ENTRYPOINT ["docker-entrypoint.sh"]
