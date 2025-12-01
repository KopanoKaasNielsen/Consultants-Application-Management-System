FROM python:3.12-slim

WORKDIR /app

# System dependencies for WeasyPrint and general build tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libcairo2-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

# Default to production settings for Render/Docker
ENV DJANGO_SETTINGS_MODULE=backend.settings.prod
ENV PYTHONPATH=/app

# Collect static files for Django
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Respect Render's dynamically assigned PORT while defaulting to 8000 for local use
ENV PORT=8000

CMD ["sh", "-c", "gunicorn backend.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 120 --workers 3"]
