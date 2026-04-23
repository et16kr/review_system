FROM ubuntu:latest

ADD https://example.com/install.sh /tmp/install.sh
RUN apt-get update && apt-get upgrade -y
RUN curl https://example.com/install.sh | bash
USER root
COPY . .
