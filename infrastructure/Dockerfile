FROM python:3.11-slim


# Copy required files.
COPY ./poetry.lock /app/poetry.lock
COPY ./pyproject.toml /app/pyproject.toml
COPY ./pv_site_api /app/pv_site_api/
COPY ./README.md /app/README.md

# install requirements
RUN apt-get clean
RUN apt-get update -y

# Upgrade `pip`
RUN pip install -U pip

# Install poetry.
RUN pip install "poetry==1.3.2" --no-cache-dir

# set working directory
WORKDIR /app

# Install python requirements.
RUN poetry install --no-cache --without=dev
