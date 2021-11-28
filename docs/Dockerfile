FROM python:3-slim
RUN apt-get update && apt-get install -y libolm-dev rsync make
COPY ./requirements.txt /
RUN pip install -r /requirements.txt && rm -f /requirements.txt
