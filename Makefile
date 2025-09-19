ENV_FILE ?= .env
PYTHON ?= python3

compose := docker compose --env-file $(ENV_FILE)

ifneq (,$(wildcard $(ENV_FILE)))
include $(ENV_FILE)
export $(shell sed -n 's/^\([A-Za-z0-9_]*\)=.*/\1/p' $(ENV_FILE))
endif

.PHONY: up down logs ps seed

up:
	$(compose) up -d --build

down:
	$(compose) down

ps:
	$(compose) ps

logs:
	$(compose) logs -f

seed:
	$(compose) exec -T postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) -f /docker-entrypoint-initdb.d/10-seed.sql
