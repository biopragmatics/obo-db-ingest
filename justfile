format:
    ruff format
    ruff check --fix --unsafe-fixes .

build:
    uv run --script build.py
