FROM python:3-alpine

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt
COPY *.py /usr/local/bin/

WORKDIR /publish
ENTRYPOINT ["/usr/local/bin/md2conf.py"]