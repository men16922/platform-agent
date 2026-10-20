FROM python:3.11-slim

RUN pip install flask --no-cache-dir

COPY app.py /app.py

USER 10001:10001

EXPOSE 8080

CMD ["python", "/app.py"]
