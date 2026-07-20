import threading
from queue import Queue

from flask import Flask, jsonify

import config
from fetcher import Fetcher
from logger import logger
from state import state
from worker import ReplayWorker

app = Flask(__name__)

sql_queue = Queue()
fetcher = None


def start_runtime():
    logger.info(
        "Starting runtime with MYSQL_HOST=%s MYSQL_PORT=%s MYSQL_DATABASE=%s MYSQL_USER=%s LOKI_URL=%s",
        config.MYSQL_HOST,
        config.MYSQL_PORT,
        config.MYSQL_DATABASE,
        config.MYSQL_USER,
        config.LOKI_URL,
    )
    global fetcher
    if getattr(app, "_runtime_started", False):
        return

    app._runtime_started = True
    fetcher = Fetcher(sql_queue, state)
    threading.Thread(target=fetcher.run, daemon=True, name="Fetcher").start()

    for i in range(config.WORKERS):
        worker = ReplayWorker(worker_id=i + 1, sql_queue=sql_queue, state_manager=state)
        threading.Thread(target=worker.run, daemon=True, name=f"Worker-{i + 1}").start()


@app.route("/")
def root():
    return jsonify({
        "service": config.APP_NAME,
        "version": config.VERSION,
        "status": "running",
    })


@app.route("/health")
def health():
    return jsonify(state.health())


@app.route("/stats")
def stats():
    return jsonify(state.stats())


@app.route("/workers")
def workers():
    return jsonify(state.workers())


@app.route("/queue")
def queue():
    return jsonify(state.queue())


@app.route("/logs")
def logs():
    return jsonify(state.logs())


if __name__ == "__main__":
    start_runtime()
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT)
