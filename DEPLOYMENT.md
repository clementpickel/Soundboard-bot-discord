# Deployment Guide

## Prerequisites

- Docker installed locally
- SSH access to remote server
- Docker installed on remote server
- `.env` file with your `DISCORD_TOKEN`

## Quick Deploy

### Linux/Mac (Bash):
```bash
chmod +x deploy.sh
./deploy.sh
```

### Windows (PowerShell):
```powershell
.\deploy.ps1
```

### Custom server:

**Bash:**
```bash
SERVER=your.server.ip USER=youruser ./deploy.sh
```

**PowerShell:**
```powershell
$env:SERVER="your.server.ip"; $env:USER="youruser"; .\deploy.ps1
# Or with parameters
.\deploy.ps1 -Server "your.server.ip" -User "youruser"
```

### If remote Docker needs sudo:

**Bash:**
```bash
REMOTE_SUDO=sudo ./deploy.sh
```

**PowerShell:**
```powershell
$env:REMOTE_SUDO="sudo"; .\deploy.ps1
# Or
.\deploy.ps1 -RemoteSudo "sudo"
```

## Configuration Options

All options can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER` | `100.119.201.30` | Remote server IP/hostname |
| `USER` | `ubuntu` | SSH username |
| `PORT` | `5000` | Host port for web interface |
| `REMOTE_DATA_DIR` | `~/soundboard-bot` | Directory for persistent data on remote (defaults to home directory). Use absolute path if ~ doesn't work: `/home/ubuntu/soundboard-bot` |
| `REMOTE_SUDO` | (empty) | Set to `sudo` if needed |
| `SSH_OPTS` | (empty) | Additional SSH options (e.g., `-i ~/.ssh/mykey`) |

## What Gets Deployed

The script will:

1. ✅ Build Docker image locally
2. ✅ Save image to tar file
3. ✅ Copy image, .env, and sounds.json to remote server
4. ✅ Load image on remote server
5. ✅ Stop and remove old container (if exists)
6. ✅ Start new container with persistent volumes
7. ✅ Clean up temporary files

## Persistent Data on Remote

Data is stored in `~/soundboard-bot/` (or `REMOTE_DATA_DIR`):
- `assets/` - Audio files (persists across deployments)
- `sounds.json` - Sound metadata (copied on first deploy, then persists)
- `.env` - Discord token (copied on deploy)

**Note:** If you get Docker volume errors with `~`, use an absolute path:
```bash
REMOTE_DATA_DIR="/home/ubuntu/soundboard-bot" ./deploy.sh
```

## Post-Deployment

### View logs:
```bash
ssh USER@SERVER 'docker logs -f soundboard-bot-container'
```

### Restart container:
```bash
ssh USER@SERVER 'docker restart soundboard-bot-container'
```

### Stop container:
```bash
ssh USER@SERVER 'docker stop soundboard-bot-container'
```

### Access web interface:
```
http://SERVER:5000
```

## Example Deployment

**Bash (Linux/Mac):**
```bash
# Deploy to custom server with sudo
SERVER=192.168.1.100 \
USER=admin \
REMOTE_SUDO=sudo \
SSH_OPTS="-i ~/.ssh/mykey" \
./deploy.sh
```

## Troubleshooting

### Permission denied on deploy.sh (Linux/Mac)
```bash
chmod +x deploy.sh
```

### Execution policy error (Windows PowerShell)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### SSH connection issues
```bash
# Test SSH connection first
ssh USER@SERVER

# Bash: Use custom SSH key
SSH_OPTS="-i ~/.ssh/mykey" ./deploy.sh

# PowerShell: Use custom SSH key
.\deploy.ps1 -SshKeyPath "C:\Users\YourUser\.ssh\mykey"
```

### Container won't start
```bash
# Check logs on remote
ssh USER@SERVER 'docker logs soundboard-bot-container'

# Check if .env is valid
ssh USER@SERVER 'cat ~/soundboard-bot/.env'
```

### Docker volume error: "includes invalid characters" or "read-only file system"
Use an absolute path instead of `~`:

**Bash:**
```bash
REMOTE_DATA_DIR="/home/ubuntu/soundboard-bot" ./deploy.sh
```

**PowerShell:**
```powershell
.\deploy.ps1 -RemoteDataDir "/home/ubuntu/soundboard-bot"
```

Or if `/opt` is read-only, use any writable directory like `/var/lib/soundboard-bot` or your home directory.

### Port already in use
**Bash:**
```bash
PORT=5001 ./deploy.sh
```

**PowerShell:**
```powershell
.\deploy.ps1 -Port "5001"
```

## Security Notes

- The `.env` file is copied to the remote server (contains bot token)
- Ensure proper file permissions on remote: `chmod 600 /opt/soundboard-bot/.env`
- Consider using Docker secrets for production
- Use firewall rules to restrict port 5000 access if needed

## Updating the Bot

Simply run the deploy script again:
```bash
./deploy.sh
```

This will:
- Build new image with latest code
- Stop old container
- Start new container
- Preserve all audio files and sounds.json
