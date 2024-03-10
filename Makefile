SHELL := /usr/bin/env bash
MAKE := make

SRC_DIR := src
DIST := dist
SRC_FILES = $(shell find $(SRC_DIR) -type f)

all: dist

init:
	poetry self add "poetry-dynamic-versioning[plugin]"
	poetry dynamic-versioning enable
	poetry install

init-dev: init
	install-glue-kernels

dist: pyproject.toml $(SRC_FILES)
	poetry dynamic-versioning enable && poetry build

clean:
	rm -rf $(DIST)

.PHONY: clean init init-dev