#!/bin/bash
cd /home/hans/Projects/HansBot
git pull

export GIT_REVISION=$(git rev-parse HEAD)
docker build -t hglad/hans-bot:latest .
docker run --restart unless-stopped --detach --env-file=env.list hglad/hans-bot:latest