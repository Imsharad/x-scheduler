.PHONY: help install run clean deploy test docker-build docker-run

help:
	@echo "X-Scheduler - Commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make run         - Run locally"
	@echo "  make clean       - Clean up __pycache__ and temp files"
	@echo "  make deploy      - Deploy to AWS"
	@echo "  make test        - Run tests"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run with Docker Compose"

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

run:
	@echo "Running X-Scheduler..."
	python src/main.py

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".DS_Store" -delete
	find . -type f -name "*.bak" -delete
	find . -type f -name "*.tmp" -delete

deploy:
	@echo "Deploying to AWS..."
	./deploy-to-aws.sh

test:
	@echo "Running tests..."
	pytest tests/

docker-build:
	@echo "Building Docker image..."
	docker build -t x-scheduler .

docker-run:
	@echo "Running with Docker Compose..."
	docker-compose up -d 