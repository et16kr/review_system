FROM python:3.12@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
USER 10001
WORKDIR /app
COPY src/app.py /app/app.py
