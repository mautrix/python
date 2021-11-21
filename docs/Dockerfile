FROM python:latest
RUN apt-get update && apt-get install -y libolm-dev
COPY ./requirements.txt /
RUN pip install -r /requirements.txt && rm -f /requirements.txt
