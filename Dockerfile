
FROM python:3.12-slim
 
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_ROOT_USER_ACTION=ignore
WORKDIR /srv
 
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
COPY . .
 
# Render sets $PORT. APP_MODULE=app.main:app switches to the full app (needs DATABASE_URL etc.).
ENV APP_MODULE=demo:app
EXPOSE 8000
CMD sh -c "uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT:-8000}"
 
