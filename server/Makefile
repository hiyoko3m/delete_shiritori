.PHONY:\
	check-all\
	run\
	format\
	test\
	lint\

check-all: test lint

run:
	docker compose up -d
	poetry run uvicorn delete_shiritori.main:app --host 0.0.0.0 --port 8000 \
		--reload --reload-dir delete_shiritori --reload-dir client

format:
	poetry run isort ./delete_shiritori ./tests
	poetry run black ./delete_shiritori ./tests

test:
	poetry run pytest tests

lint:
	poetry run mypy ./delete_shiritori ./tests
	poetry run flake8 ./delete_shiritori ./tests

