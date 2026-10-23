# TensorFlow's supported Linux wheels require glibc; use slim instead of
# Alpine so the Basic-LSTM runtime can be installed in the production image.
FROM python:3.12.7-slim

RUN pip install --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY . /app
WORKDIR /app

RUN pip install -e .

RUN crontab -u root crontab.txt

CMD ["crond", "-f"]