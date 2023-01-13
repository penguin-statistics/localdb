<img src="https://penguin.upyun.galvincdn.com/logos/penguin_stats_logo.png"
     alt="Penguin Statistics - Logo"
     width="96px" />

# Penguin Statistics - LocalDB

[![License](https://img.shields.io/github/license/penguin-statistics/localdb)](https://github.com/penguin-statistics/localdb/blob/dev/LICENSE)

## Usage

### Prerequisites

1. [Install `just`](https://github.com/casey/just#packages)
   > `just` is a task runner inspired by `make` and `npm run`. It is designed to be an extremely simple way to define and run tasks. It is written in Rust, and is available on Windows, macOS, and Linux.
2. `cp .env.example .env` and put AWS credentials into `.env`

### Usage

Use `just start` to start the LocalDB. LocalDB script will properly initialize the PostgreSQL Database within the container, restore the latest backup from AWS S3 using pgbackrest, and start the PostgreSQL server in the container.

You will need to use the same DB credential as of the production DB. Efforts may be made to make the DB credential configurable in the future.

## Development

Use `just dev` to start the LocalDB in development mode. This will first clear the development database volume, initialize the database, then it will fetch the `debug` backup from AWS S3 and restore it.

We are using the `debug` backup instead of the `prod` backup. The `debug` backup is a deadly simple backup that only contains a `postgres.testtable` with 3 rows of testing data. This is to make the development process much faster and also saves bandwidth.
