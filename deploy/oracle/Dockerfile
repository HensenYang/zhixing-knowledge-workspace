FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements-lock.txt /app/backend/requirements-lock.txt
RUN pip install --no-cache-dir -r /app/backend/requirements-lock.txt \
    && useradd --uid 10001 --create-home workspace \
    && mkdir /data && chown workspace:workspace /data
COPY backend /app/backend
COPY database /app/database
COPY scripts/migrate.py /app/scripts/migrate.py
COPY deploy/oracle/runtime.py /app/deploy/oracle/runtime.py
USER workspace
EXPOSE 8001
CMD ["python", "-m", "deploy.oracle.runtime", "serve"]
