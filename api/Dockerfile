FROM python:3.10-slim

WORKDIR /app

RUN pip install fastapi uvicorn psycopg2-binary bcrypt pyjwt redis

COPY api.py .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
