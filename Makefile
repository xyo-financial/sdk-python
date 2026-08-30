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
	# Generate aside and copy the subtree in: -o is the root the package is written
	# under, so pointing it at the package directory nests the output, and pointing
	# it at src/ overwrites the hand-written src/xyo/__init__.py.
	rm -rf /tmp/py-gen
	npx -y @openapitools/openapi-generator-cli generate \
		-i ../specs/openapi.yml \
		-g python \
		-o /tmp/py-gen \
		--additional-properties=packageName=xyo._generated,library=httpx,generateSourceCodeOnly=true \
		--global-property apiTests=false,modelTests=false,apiDocs=false,modelDocs=false
	rm -rf src/xyo/_generated
	mkdir -p src/xyo/_generated
	cp -a /tmp/py-gen/xyo/_generated/. src/xyo/_generated/
	rm -rf /tmp/py-gen

docker-build:
	docker build -t xyo-sdk-python:latest .

docker-test:
	docker build --target test -t xyo-sdk-python:test .
