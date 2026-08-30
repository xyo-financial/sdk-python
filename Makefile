.PHONY: all test lint format typecheck check build clean spec-check docker-build docker-test

all: check test

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy src/xyo

check: lint typecheck test

build:
	python3 -m pip install --upgrade build
	python3 -m build

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .coverage coverage.xml .mypy_cache .ruff_cache

spec-check:
	python3 scripts/check_spec_coverage.py ../specs/openapi.yml

docker-build:
	docker build -t xyo-sdk-python:latest .

docker-test:
	docker build --target test -t xyo-sdk-python:test .
