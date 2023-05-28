FROM python:3.9-slim
MAINTAINER Hans Erlend Bakken Glad "hanseglad@gmail.com"

RUN apt-get update && apt-get install -y git

# Install dependencies for cryptography and PGPy
# RUN apt-get update && apt-get install -y build-essential libssl-dev libffi-dev python3-dev cargo && rm -rf /var/lib/apt/lists/*

ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY ./* /bot/
WORKDIR /bot

CMD ["python", "bot.py"]

ARG GIT_REVISION
LABEL git-revision=$GIT_REVISION