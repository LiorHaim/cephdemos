FROM registry.redhat.io/ubi8/python-36
ADD requirements.txt .
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt
ADD exporter.py .
EXPOSE 80
ENTRYPOINT ["python","exporter.py"]
