FROM python:3.11-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

FROM python:3.11-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app ./app
COPY sample_input.json ./sample_input.json
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
RUN mkdir -p /app/artifacts && chown -R appuser:appuser /app
USER appuser
ENV ARTIFACTS_DIR=/app/artifacts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
