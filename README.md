# Soundboard-bot-discord
I'm not paying 10€/month for a soundboard so I'm building my own with a web interface and interactive Discord buttons!

## Features

✨ **Web Interface** - Upload and manage sounds through a beautiful web UI at http://localhost:5000
🎵 **Dynamic Soundboard** - Shows up to 25 sounds with customizable buttons in Discord
🎮 **Interactive Buttons** - Click buttons to play sounds instantly
🔊 **Multiple Audio Formats** - Supports mp3, wav, ogg, and flac
📝 **Sound Metadata** - Set title, emoji, and visibility for each sound
⚡ **Instant Updates** - Changes appear immediately with guild-specific command sync

## Quick Start

### Option 1: Docker (Recommended) 🐳

1. **Install Docker Desktop**
   - Download from https://www.docker.com/products/docker-desktop/

2. **Run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

3. **Access the web interface:**
   Open http://localhost:5000 in your browser

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

### Option 2: Local Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install FFmpeg** (required for audio playback):
   - Windows: `choco install ffmpeg`
   - Or download from https://ffmpeg.org/download.html

3. **Run the bot:**
   ```bash
   python bot.py
   ```

4. **Access the web interface:**
   Open http://localhost:5000 in your browser to upload and manage sounds

## Discord Commands

- `/soundboard` - Display interactive soundboard with up to 25 sound buttons
- `/help` - Show all available commands and web interface link
- `/update` - Re-sync commands and reload sounds (use if new sounds don't appear)
- `/join` - Join the Lobby voice channel
- `/play` - Play test.mp3
- `/leave` - Disconnect from voice

## Web Interface

The web interface at http://localhost:5000 allows you to:

- **Upload new sounds** with customizable:
  - Title (display name)
  - Emoji (button icon)
  - showInButton (whether it appears in `/soundboard`)
- **View all uploaded sounds** with their metadata
- **Delete sounds** you no longer need

Only sounds with `showInButton=true` will appear in the Discord `/soundboard` command (max 25).

## How It Works

1. Upload sounds via the web interface
2. Set metadata (title, emoji, showInButton)
3. Use `/soundboard` in Discord to see buttons for all sounds where showInButton is true
4. Click any button to play that sound in the Lobby voice channel
5. If new sounds don't appear, use `/update` to re-sync the commands

The bot stores sound metadata in `sounds.json` and audio files in the `assets/` folder.

## Deployment

Deploy to a remote server with one command:

**Linux/Mac:**
```bash
chmod +x deploy.sh
./deploy.sh
```

**Windows:**
```powershell
.\deploy.ps1
```

Or with custom settings:
```bash
SERVER=your.server.ip USER=youruser ./deploy.sh
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions and configuration options.
