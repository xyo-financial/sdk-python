.PHONY: all test lint format typecheck check build clean generate docker-build docker-test

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

generate:
	npx -y @openapitools/openapi-generator-cli generate \
		-i ../specs/openapi.yml \
		-g python \
		-o ./src/xyo/_generated \
		--additional-properties=packageName=xyo._generated,library=httpx,generateSourceCodeOnly=true \
		--global-property apiTests=false,modelTests=false,apiDocs=false,modelDocs=false

docker-build:
	docker build -t xyo-sdk-python:latest .

docker-test:
	docker build --target test -t xyo-sdk-python:test .
