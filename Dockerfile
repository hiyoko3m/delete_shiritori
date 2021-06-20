FROM python:3.9 AS exporter
COPY ./server/poetry.lock /poetry.lock
COPY ./server/pyproject.toml /pyproject.toml
RUN pip install poetry
RUN poetry export -f requirements.txt > requirements.txt

FROM python:3.9 AS builder
COPY --from=exporter /requirements.txt /requirements.txt
RUN pip3 install -r requirements.txt

FROM python:3.9-slim AS runner
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
WORKDIR /app
COPY ./server/delete_shiritori /app/delete_shiritori
COPY ./client/build /app/client
EXPOSE 80
CMD ["/usr/local/bin/uvicorn", "delete_shiritori.main:app", "--host", "0.0.0.0", "--port", "80"]
