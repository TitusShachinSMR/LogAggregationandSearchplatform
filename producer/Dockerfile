FROM python:3.10-slim

WORKDIR /app

RUN pip install redis

COPY producer.py .

CMD ["python", "producer.py"]
