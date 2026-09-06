This is a Discord bot that supports audio streaming. WIP.

### Building and running the image
Make sure you are in the same folder as the Dockerfile.
Create a file "env.list" and add the Discord token for your bot inside it:
```
DISCORD_TOKEN=<token for your Discord bot>
```
Build and start the bot with Docker Compose:
```
docker compose up --build --detach
```

This builds `hglad/hans-bot:latest` and runs it as the `eggbot` container with
the `unless-stopped` restart policy.
