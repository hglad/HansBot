FROM python:3.9-slim
MAINTAINER Hans Erlend Bakken Glad "hanseglad@gmail.com"

RUN apt-get update
RUN apt-get install -y git ffmpeg
ADD requirements.txt requirements.txt
ADD bot.py bot.py
ADD env.list env.list

RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
