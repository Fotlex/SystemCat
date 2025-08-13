ENV=prod

COMPOSE_FILE = .docker/docker-compose.prod.yaml
ENV_FILE = .env
DOCKER_COMPOSE = docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)

-include $(ENV_FILE)

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\036m%-30s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "To use 'prod' environment, append 'ENV=prod' (e.g., make up ENV=prod)"


# --------------- GENERAL COMMANDS --------------- #


.PHONY: build
build:
	@echo "Building Docker images for $(ENV) environment..."
	@$(DOCKER_COMPOSE) build

.PHONY: up
up:
	@echo "Starting Docker containers for $(ENV) environment..."
	@$(DOCKER_COMPOSE) up -d

.PHONY: up-logs
up-logs:
	@echo "Starting Docker containers with logs for $(ENV) environment..."
	@$(DOCKER_COMPOSE) up

.PHONY: logs
logs:
	@$(DOCKER_COMPOSE) logs -f

.PHONY: down
down:
	@echo "Stopping and removing Docker containers for $(ENV) environment..."
	@$(DOCKER_COMPOSE) down

.PHONY: clean
clean:
	@echo "WARNING: This will remove ALL containers, images, and volumes for $(ENV) environment. Data will be lost."
	@bash -c 'read -p "Are you sure? (y/N) " confirm; \
 	if [ "$$confirm" = "y" ]; then \
		echo "Proceeding with clean for $(ENV) environment..."; \
  		$(DOCKER_COMPOSE) down --rmi all -v --volumes --remove-orphans; \
 	else \
  		echo "Clean operation cancelled."; \
  		exit 1; \
 	fi'

.PHONY: restart
restart:
	@echo "Restarting Docker containers for $(ENV) environment..."
	@$(DOCKER_COMPOSE) restart


# --------------- BACKEND COMMANDS --------------- #


.PHONY: migrate
migrate:
	@echo "Running migrations for $(ENV) environment..."
	@$(DOCKER_COMPOSE) exec web python manage.py migrate --noinput

.PHONY: makemigrations
makemigrations:
	@$(DOCKER_COMPOSE) exec web python manage.py makemigrations $(APP)


.PHONY: collectstatic
collectstatic:
	@echo "Collecting static files for $(ENV) environment..."
	@$(DOCKER_COMPOSE) exec app python project/manage.py collectstatic --noinput


.PHONY: base_commands
base_commands:
	@echo "Collecting static files for $(ENV) environment..."
	@$(DOCKER_COMPOSE) exec web python manage.py migrate --noinput
	@$(DOCKER_COMPOSE) exec web python manage.py collectstatic --noinput
	@$(DOCKER_COMPOSE) exec web python manage.py createsuperuser


.PHONY: super_user
super_user:
	@echo "Collecting static files for $(ENV) environment..."
	@$(DOCKER_COMPOSE) exec web python manage.py createsuperuser


.PHONY: shell
shell:
	@$(DOCKER_COMPOSE) exec app bash

.PHONY: dbshell
dbshell:
	@$(DOCKER_COMPOSE) exec app python project/manage.py dbshell

.PHONY: celery-worker-shell
celery-worker-shell:
	@$(DOCKER_COMPOSE) exec celery_worker bash

.PHONY: bot-shell
bot-shell:
	@$(DOCKER_COMPOSE) exec bot bash