FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml ./
COPY unbound ./unbound
RUN pip install --no-deps . && useradd --uid 10001 --create-home unbound && mkdir /app/data && chown unbound:unbound /app/data
USER unbound
EXPOSE 8000
CMD ["uvicorn", "unbound.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
