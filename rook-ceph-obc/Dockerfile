# docker build -t ubuntu1604py36
FROM python:3.8-slim-buster

# install needed pip packages
WORKDIR /usr/src/app
COPY upload.py ./
COPY requirements.txt ./
RUN pip3 install --upgrade -r requirements.txt

# run script from entry point
ENTRYPOINT [ "python3", "./upload.py" ]
