FROM jmayfield/shellish

COPY requirements.txt /
RUN pip install -r /requirements.txt
COPY . /package
RUN cd /package && python ./setup.py install

ENTRYPOINT ["ecm"]
