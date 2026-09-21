FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/alembic.ini backend/pytest.ini ./
COPY backend/migrations ./migrations
COPY backend/tests ./tests
COPY worker ./worker
COPY config ./config
RUN useradd --create-home --uid 10001 news
USER news
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]