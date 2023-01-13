import argparse
import os
import subprocess
import sys
from enum import Enum

from colorama import Back, Fore, Style
from prompt_toolkit import prompt
from pydantic import BaseModel


class CommandException(Exception):
    pass


def log(msg):
    msg = "  >> " + msg
    banner_signature = "[ Penguin LocalDB ]"
    banner_width = 80
    # center the banner signature
    banner_padding = (banner_width - len(banner_signature)) // 2
    banner_top = " " * banner_padding + banner_signature + \
        " " * (banner_width - len(banner_signature) - banner_padding)

    print()
    print(Back.CYAN + Fore.WHITE + banner_top + Style.RESET_ALL)
    print(Fore.GREEN + Style.BRIGHT + msg + Style.RESET_ALL)
    print(Back.CYAN + Fore.WHITE + " " * len(banner_top) + Style.RESET_ALL)
    print()


def parse_args():
    parser = argparse.ArgumentParser(prog="penguin-localdb-entry")

    parser.add_argument('--backup-source',
                        choices=['debug', 'prod'], default='debug')
    parser.add_argument(
        '--pgdata', default='/var/lib/postgresql/data')
    return parser.parse_args()


args = parse_args()

PGBACKREST_CONFIG_FORMAT = """
[main]
pg1-path=/var/lib/postgresql/data

[global]
process-max=2
repo1-bundle=y
repo1-type=s3
repo1-path={s3_path}
{aws_settings}

# Force a checkpoint to start backup immediately.
start-fast=y
# Use delta restore.
delta=y

# Enable ZSTD compression.
compress-type=zst
compress-level=6

log-level-console=info
log-level-file=debug

[global:archive-push]
compress-level=4
"""


def print_func_name():
    log(f"Running {sys._getframe(1).f_code.co_name}...")


class AWSSettings(BaseModel):
    access_key: str
    secret_key: str
    region: str
    bucket: str

    def format_yaml(self):
        return f"""\
        repo1-s3-key={self.access_key}
        repo1-s3-key-secret={self.secret_key}
        repo1-s3-region={self.region}
        repo1-s3-bucket={self.bucket}
        repo1-s3-endpoint=s3.amazonaws.com
        """


class BackupS3Path(str, Enum):
    debug = "/pgbackrest-test"
    prod = "/penguin-db/pgbackrest"


def format_pgbackrest(settings: AWSSettings, env: BackupS3Path):
    return PGBACKREST_CONFIG_FORMAT.format(aws_settings=settings.format_yaml(), s3_path=env.value)


PGBACKREST_CONFIG = "/etc/pgbackrest.conf"
DOCKER_ENTRYPOINT = "/usr/local/bin/docker-entrypoint.sh"
DOCKER_ENTRYPOINT_ENV = {"POSTGRES_PASSWORD": "root",
                         "POSTGRES_HOST_AUTH_METHOD": "trust"}
ENV_BIN = "/usr/bin/env"


def env_or_ask(key, **kwargs):
    if key in os.environ:
        return os.environ[key]
    else:
        return prompt(f"{key}: ", **kwargs)


def write_pgbackrest_config():
    print_func_name()

    aws_settings = AWSSettings(
        access_key=env_or_ask("AWS_ACCESS_KEY"),
        secret_key=env_or_ask("AWS_SECRET_KEY"),
        region="ap-southeast-1",
        bucket=env_or_ask("AWS_BUCKET"),
    )

    with open(PGBACKREST_CONFIG, "w") as f:
        f.write(format_pgbackrest(aws_settings,
                BackupS3Path[args.backup_source]))


def exec_subprocess(cmd, **kwargs):
    log(f"exec_subprocess: Running subprocess command: \"{' '.join(cmd)}\"")
    # start subprocess, redirect its stdout and stderr to this process
    # so that we can capture its output
    # then, wait for the process to finish
    proc = subprocess.Popen([ENV_BIN, *cmd], **kwargs)
    proc.communicate()
    returncode = proc.returncode
    if returncode != 0:
        raise CommandException(
            f"Failed to run command: {' '.join(cmd)}: Unexpected return code: {returncode}")

    return returncode


def exec_pgbackrest(cmd, **kwargs):
    return exec_subprocess(["pgbackrest", "--stanza=main", *cmd], **kwargs)


def check_pgbackrest_info():
    print_func_name()
    exec_pgbackrest(["info"])


def exec_postgres_docker_entrypoint():
    print_func_name()
    # listen on subprocess's stdout and stderr
    # if stdout contains string 'database system is ready to accept connections'
    # then we know that postgres is ready
    # proceed to send a SIGINT to the subprocess to shutdown postgres immediately after.
    os_env_copy = os.environ.copy()
    # remove PGDATA from os_env_copy
    os_env_copy.pop("PGDATA", None)
    os_env_copy["PGDATA"] = args.pgdata

    proc = subprocess.Popen(
        [ENV_BIN, "bash", DOCKER_ENTRYPOINT, "postgres"], env={
            **DOCKER_ENTRYPOINT_ENV,
            **os_env_copy,  # inherit all env vars: original Dockerfile specifies envs like PGDATA that is necessary to run the script
        }, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    init_completed = False

    while True:
        line = proc.stdout.readline()
        if line == b'':
            break
        decoded = line.decode("utf-8")
        print(decoded, end="")
        if "PostgreSQL init process complete" in decoded:
            log("Postgres initialized. Waiting for postgres to start again.")
            init_completed = True
        elif init_completed and "database system is ready to accept connections" in decoded:
            log("Postgres is ready to accept connections: sending SIGINT to shutdown postgres immediately.")
            proc.send_signal(subprocess.signal.SIGINT)
        elif init_completed and "database system is shut down" in decoded:
            log("Postgres has been shutdown.")

    try:
        proc.wait(timeout=3)
        proc.kill()
    except subprocess.TimeoutExpired as e:
        log("Postgres process did not exit in 3 seconds despite declaring stopped. Printing the process tree for debug...")
        exec_subprocess(["pstree", "-ahltpu"])
        raise e

    returncode = proc.returncode
    if returncode != 0:
        raise CommandException(
            f"Failed to run command: {DOCKER_ENTRYPOINT}: Unexpected return code: {returncode}")

    return returncode


def clear_postgres_pgdata_dir():
    print_func_name()
    exec_subprocess(["rm", "-rf", args.pgdata + "/*"])


def print_pgdata_stats():
    exec_subprocess(
        ["ls", "-l", f"{args.pgdata}"])
    try:
        exec_subprocess(
            ["bash", "-c", "cat /var/lib/postgresql/data/*.conf"])
    except CommandException as e:
        print(e)


def fix_postgres_conf_permissions():
    print_func_name()
    exec_subprocess(
        ["bash", "-c", f"chown --reference={args.pgdata}/PG_VERSION {args.pgdata}/*.conf"])
    exec_subprocess(
        ["bash", "-c", f"chmod --reference={args.pgdata}/PG_VERSION {args.pgdata}/*.conf"])


def backup_postgres_conf():
    print_func_name()
    exec_subprocess(["mkdir", "-p", "/tmp/pgconfbackup"])
    exec_subprocess(
        ["bash", "-c", f"cp -r {args.pgdata}/*.conf /tmp/pgconfbackup"])
    print_pgdata_stats()


def restore_postgres_conf():
    print_func_name()
    # restore configuration, but do not override existing files.
    exec_subprocess(
        ["bash", "-c", f"cp -r /tmp/pgconfbackup/*.conf {args.pgdata}"])
    exec_subprocess(
        ["rm", "-rf", "/tmp/pgconfbackup"])
    fix_postgres_conf_permissions()
    print_pgdata_stats()


def exec_pgbackrest_restore():
    print_func_name()
    exec_pgbackrest(["restore", "--archive-mode", "off"])


def start_postgres():
    print_func_name()
    exec_subprocess(["gosu", "postgres", "postgres"])


# def temp():
#     print_func_name()
#     content_to_append = """
#     archive_mode = 'off'
#     restore_command = 'pgbackrest --stanza=main archive-get %f "%p"'
#     """
#     # append content_to_append to postgresql.conf in args.pgdata
#     with open(f"{args.pgdata}/postgresql.conf", "a") as f:
#         f.write(content_to_append)


def main():
    # temp()
    print_pgdata_stats()
    write_pgbackrest_config()
    exec_postgres_docker_entrypoint()
    print_pgdata_stats()
    backup_postgres_conf()
    check_pgbackrest_info()
    print_pgdata_stats()
    # clear_postgres_pgdata_dir()
    exec_pgbackrest_restore()
    print_pgdata_stats()
    restore_postgres_conf()
    start_postgres()


if __name__ == "__main__":
    main()
