FROM python:3.12.7-slim-bullseye

# upgrade pip
RUN pip install --upgrade pip

# get curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# permissions and nonroot user for tightened security
RUN adduser --disabled-password --gecos "" nonroot
RUN mkdir /home/app/ && chown -R nonroot:nonroot /home/app
RUN mkdir -p /var/log/backend-app && touch /var/log/backend-app/backend-app.err.log && touch /var/log/backend-app/backend-app.out.log
RUN chown -R nonroot:nonroot /var/log/backend-app
WORKDIR /home/app
USER nonroot

# copy all the files to the container
COPY --chown=nonroot:nonroot . .

# venv
ENV VIRTUAL_ENV=/home/app/venv

# python setup
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN export BACKEND_APP=app.py
RUN pip install --no-cache-dir --force-reinstall -r requirements.txt
RUN pip install polars-lts-cpu --force-reinstall


# define the port number the container should expose
EXPOSE 8000

CMD ["gunicorn", "-w 3", "-t 60", "-b 0.0.0.0:8000", "app:app"]