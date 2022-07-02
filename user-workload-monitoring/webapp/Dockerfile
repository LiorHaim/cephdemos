FROM registry.redhat.io/ubi8/python-36
ADD requirements.txt .
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt
ADD app.py .
EXPOSE 5000
ENTRYPOINT ["python","app.py"]
