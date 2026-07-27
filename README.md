# MySQL Buffer Pool Warmer

This service reads SQL statements from Loki, places them into a shared in-memory queue, and replays them against a MySQL instance using worker threads.

## What it does

1. The fetcher calls Loki and reads log streams.
2. It extracts SQL statements that look like SELECT queries.
3. Each extracted query is pushed into a queue.
4. Worker threads read from the queue and execute the query against MySQL.
5. The service exposes HTTP endpoints to inspect health, queue size, workers, and recent logs.

## Architecture

- app.py
  - Starts Flask.
  - Creates the shared queue.
  - Starts the fetcher thread and worker threads.
- fetcher.py
  - Pulls data from Loki.
  - Extracts SQL text from log entries.
  - Pushes query payloads into the queue.
- worker.py
  - Connects to MySQL.
  - Consumes one query at a time from the queue.
  - Executes it on the MySQL target.
- state.py
  - Keeps shared runtime state such as queue size, worker states, and metrics.
- config.py
  - Holds Loki, MySQL, Flask, and logging configuration.

## Flow

1. Loki receives logs from your MySQL environment.
2. The fetcher queries Loki using the configured query expression.
3. Each matching log line is parsed to find a SQL statement.
4. The SQL statement is enqueued.
5. Workers pop the statement and replay it against the target MySQL database.
6. Each worker updates the shared state with success/failure information.

## Endpoints

- GET /health
  - Returns service health information.
- GET /stats
  - Returns replay metrics and execution statistics.
- GET /workers
  - Returns worker status.
- GET /queue
  - Returns queue depth information.
- GET /logs
  - Returns recent application log entries.

## Configuration

The service reads its configuration from environment variables.

### Required variables

- LOKI_URL
  - Loki endpoint used by the fetcher, for example `http://loki:3100`
- LOKI_QUERY
  - Loki query used to select relevant SQL log lines from logs
- MYSQL_HOST
  - Target MySQL host
- MYSQL_PORT
  - Target MySQL port
- MYSQL_DATABASE
  - Target MySQL database
- MYSQL_USER
  - MySQL username
- MYSQL_PASSWORD
  - MySQL password
- WORKERS
  - Number of replay worker threads

### Optional variables

- LOKI_LIMIT
  - Maximum number of log entries fetched from Loki per request
- LOKI_LOOKBACK_HOURS
  - How far back to query logs in hours for each fetch cycle
- LOKI_REQUEST_TIMEOUT
  - Maximum seconds to wait for Loki to respond
- LOKI_RETRY_COUNT
  - Number of retry attempts if a Loki request fails
- LOKI_RETRY_DELAY
  - Seconds to wait between Loki retry attempts
- POLL_INTERVAL
  - Time in seconds between Loki fetch cycles
- FLASK_HOST
  - Host used by the Flask web server
- FLASK_PORT
  - Port used by the Flask web server
- LOG_LEVEL
  - Logging level for the app
- LOG_FILE
  - File path for logs if file logging is enabled

## Run with Docker Compose

Copy `.env.example` to `.env` and update the values as needed.

```bash
cp .env.example .env
docker compose up --build -d
```

Then open:

- http://localhost:5000/health

## Notes

- The queue is in-memory only, so it is not durable.
- The current implementation focuses on replaying SELECT statements.
- If Loki returns non-SQL log lines, they are ignored.
- Use a narrow Loki query to reduce noise and keep replay traffic focused.
