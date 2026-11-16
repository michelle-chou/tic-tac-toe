FROM python:3.13-slim-bookworm
ARG VERSION=4.0.0

RUN apt-get update -qq
RUN apt-get install -y build-essential default-libmysqlclient-dev default-mysql-client imagemagick libmagickwand-dev curl git sudo apt-transport-https unzip cmake vim jq wget

RUN echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && (sudo sysctl -p || true)

RUN curl -sL https://deb.nodesource.com/setup_14.x | bash - \
       && apt-get install -y nodejs=14.21.3-deb-1nodesource1

RUN useradd -u 1000 --create-home -d /app --shell /bin/bash cryo \
      && adduser cryo sudo

RUN apt-get install -y openssh-client

ENV APP_HOME /app
RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME
