FROM postgres:14

WORKDIR /app

# Install packages
RUN apt-get update && apt-get install --no-install-recommends -y \
    sudo \
    jq \
    curl \
    unzip \
    awscli \
    pgbackrest \
    python3 \
    python3-distutils \
    psmisc \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

COPY pyproject.toml /app/
COPY poetry.lock /app/

RUN /root/.local/bin/poetry install

COPY app /app/

EXPOSE 5432

ENTRYPOINT ["/root/.local/bin/poetry", "run", "python", "/app/entry.py"]
