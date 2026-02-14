# Docker Quick Start Guide

## Prerequisites
- Docker Desktop installed (https://www.docker.com/products/docker-desktop/)
- Discord bot token in `.env` file

## Option 1: Using Docker Compose (Recommended)

### Build and Start
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f
```

### Stop
```bash
docker-compose down
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

## Option 2: Using Docker Commands

### Build Image
```bash
docker build -t soundboard-bot .
```

### Run Container
```bash
docker run -d \
  --name soundboard-bot \
  -p 5000:5000 \
  -v ${PWD}/assets:/app/assets \
  -v ${PWD}/sounds.json:/app/sounds.json \
  -v ${PWD}/.env:/app/.env:ro \
  soundboard-bot
```

### View Logs
```bash
docker logs -f soundboard-bot
```

### Stop Container
```bash
docker stop soundboard-bot
docker rm soundboard-bot
```

## Access

- **Web Interface:** http://localhost:5000
- **Discord Bot:** Will connect automatically using token from `.env`

## Persistent Data

The following are mounted as volumes and will persist after container restarts:
- `assets/` - Audio files
- `sounds.json` - Sound metadata database

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs

# Or for standalone container
docker logs soundboard-bot
```

### Permission issues
```bash
# Fix permissions on Linux/Mac
chmod -R 755 assets/
```

### Rebuild completely
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Production Deployment

For production, consider:
1. Using a reverse proxy (nginx) for the web interface
2. Setting up proper SSL/TLS
3. Using Docker secrets for the bot token instead of `.env`
4. Setting resource limits in docker-compose.yml
