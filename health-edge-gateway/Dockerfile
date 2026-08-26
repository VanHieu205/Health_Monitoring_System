FROM python:3.10-slim-bullseye
WORKDIR /app
COPY pyproject.toml poetry.lock* /app/
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-root
COPY src /app/src
CMD ["python", "src/api/grpc_server.py"]
