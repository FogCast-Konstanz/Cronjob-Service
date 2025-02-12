FROM python:3.12.7-alpine

RUN pip install --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY . /app
WORKDIR /app

RUN pip install -e .

RUN crontab -u root crontab.txt

CMD ["crond", "-f"]