FROM ubuntu:22.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


RUN apt-get update -y
RUN apt-get install -y gcc default-libmysqlclient-dev pkg-config git
RUN apt-get install mysql-client -y
RUN apt-get install graphviz graphviz-dev -y
RUN apt-get install python3 -y
RUN apt-get install python3-pip -y
RUN python3 -m pip install --upgrade pip
RUN pip3 install pipenv


WORKDIR /home/python
COPY /src .
COPY Pipfile .
COPY Pipfile.lock .
RUN pipenv requirements > requirements.txt
RUN pip3 install -r requirements.txt
COPY /gunicorn/gunicorn.py .
ENV PATH="/home/python/.local/bin:${PATH}"
EXPOSE 8000
CMD ["gunicorn", "epiportal.wsgi:application", "-c", "gunicorn.py"]
