#!/bin/bash
set -e

cd /home/hans/Projects/HansBot
git pull

# Remove the container created by the previous docker run-based deployment.
if docker container inspect eggbot >/dev/null 2>&1; then
    compose_project=$(docker container inspect \
        --format '{{ index .Config.Labels "com.docker.compose.project" }}' eggbot)
    if [ -z "$compose_project" ] || [ "$compose_project" = "<no value>" ]; then
        docker container rm --force eggbot
    fi
fi

docker compose up --build --detach --remove-orphans
