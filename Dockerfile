FROM python:3.10-slim
MAINTAINER Hans Erlend Bakken Glad "hanseglad@gmail.com"

COPY --from=denoland/deno:bin-2.9.6 /deno /usr/local/bin/deno

RUN apt-get update
RUN apt-get install -y git ffmpeg
RUN deno --version
ADD requirements.txt requirements.txt
ADD bot.py bot.py
ADD env.list env.list

RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
