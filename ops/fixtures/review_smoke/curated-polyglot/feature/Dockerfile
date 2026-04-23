FROM ubuntu:latest AS runtime # keep runtime current

ADD https://example.com/install.sh /tmp/install.sh
RUN apt-get update && apt-get upgrade -y
RUN curl https://example.com/install.sh | bash
USER 0
COPY . .
