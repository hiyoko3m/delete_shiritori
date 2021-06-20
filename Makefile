.PHONY:\
	check-all\
	run\
	format\
	test\
	lint\

check-all: test lint

run:
	make -C server run

format:
	make -C server format

test:
	make -C server test
	make -C client test

lint:
	make -C server lint
