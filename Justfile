# dev:
#     docker build -t "penguin-localdb-dev" .
#     docker run --name "penguin-localdb-dev" -it --rm -p 15432:5432 --env-file ./.env "penguin-localdb-dev" --backup-source debug

# dev-persisted:
#     docker volume create "penguin-localdb-dev-volume"
#     docker build -t "penguin-localdb-dev" .
#     docker run --name "penguin-localdb-dev" -it --rm -p 15432:5432 --env-file ./.env --mount source="penguin-localdb-dev-volume",target=/var/lib/postgresql/data "penguin-localdb-dev" --backup-source debug

# start:
#     docker volume create "penguin-localdb-volume"
#     docker build -t "penguin-localdb" .
#     docker run --name "penguin-localdb" -it --rm -p 15432:5432 --env-file ./.env --mount source="penguin-localdb-volume",target=/var/lib/postgresql/data "penguin-localdb" --backup-source prod

dev:
    docker compose -f compose-debug.yml down
    docker compose -f compose-debug.yml up --force-recreate --build

fresh-dev:
    docker compose -f compose-debug.yml down
    -docker volume rm penguin-local-db_postgres-dev
    docker compose -f compose-debug.yml up --force-recreate --build

fresh-prod:
    docker compose -f compose-prod.yml down
    -docker volume rm penguin-local-db_postgres
    docker compose -f compose-prod.yml up --force-recreate --build

start:
    docker compose -f compose-prod.yml up --force-recreate --build

stop:
    docker compose -f compose-prod.yml stop

prune:
    docker compose -f compose-prod.yml down
