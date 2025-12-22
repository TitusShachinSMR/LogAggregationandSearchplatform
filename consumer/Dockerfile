FROM python:3.10-slim

WORKDIR /app

RUN pip install redis psycopg2-binary

COPY consumer.py .

CMD ["python", "consumer.py"]
