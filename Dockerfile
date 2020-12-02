FROM python:3-alpine

ADD requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt
ADD md2conf.py /usr/local/bin/md2conf

WORKDIR /publish
ENTRYPOINT ["/usr/local/bin/md2conf"]