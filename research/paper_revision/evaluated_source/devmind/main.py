"""Entrypoints for the web control plane and independent execution workers."""

import argparse
import json
import logging
import os
import signal
import threading
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

from devmind.api import create_app
from devmind.config import load
from devmind.database import Repository
from devmind.readiness import inspect
from devmind.runner import Runner


def main() -> None:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="DevMind research control plane")
    parser.add_argument("mode", choices=["init", "serve", "worker", "doctor"])
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    config = load()
    database_url = make_url(config.database)
    if database_url.get_backend_name() == "sqlite":
        filename = database_url.database
        if filename and filename != ":memory:":
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
    repository = Repository(config.database)
    if args.mode == "init":
        repository.initialize()
        print("Database schema initialized")
    elif args.mode == "serve":
        repository.check_schema()
        uvicorn.run(
            create_app(config, repository),
            host=args.host,
            port=args.port,
            access_log=False,
        )
    elif args.mode == "doctor":
        report = inspect(config, repository)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["ready"] else 1)
    else:
        repository.check_schema()
        stopping = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stopping.set())
        runner = Runner(config, repository, shutdown=stopping)
        while not stopping.is_set():
            work = runner.once()
            if args.once:
                return
            if not work:
                stopping.wait(1)


if __name__ == "__main__":
    main()
