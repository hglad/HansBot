#!/bin/bash
cd /home/hans/Projects/HansBot
git pull
docker build -t hglad/hans-bot:latest .
docker kill $(docker ps -q)
docker run --restart unless-stopped --detach --env-file=env.list hglad/hans-bot:latest