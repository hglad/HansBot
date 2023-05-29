# An music bot
One of the Discord music bots of all time

### Building and running the image
Make sure you are in the same folder as the Dockerfile.
Create a file "env.list" and add the Discord token for your bot inside it:
```
DISCORD_TOKEN=<token for your Discord bot>
```
then build the Docker image with:
```
docker build -t hglad/hans-bot:<some-tag> .
```
Run it:
```
docker run --restart unless-stopped --detach --env-file=env.list hglad/hans-bot:<some-tag>
```

`--restart unless-stopped` will spawn a new container if the container dies.

`--detach` makes it run in the background.

