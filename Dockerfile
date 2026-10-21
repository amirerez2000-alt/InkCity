FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# תלויות מערכת ההפעלה הנדרשות ל-Pillow
RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "inkcitycore.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
