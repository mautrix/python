FROM python:latest
RUN apt-get update && apt-get install -y libolm-dev rsync
COPY ./requirements.txt /
RUN pip install -r /requirements.txt && rm -f /requirements.txt
