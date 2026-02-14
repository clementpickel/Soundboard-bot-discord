# Discord Soundboard Bot Setup

## Prerequisites

1. **Python 3.8 or higher** installed
2. **FFmpeg** installed and added to PATH
   - Download from: https://ffmpeg.org/download.html
   - Or install via chocolatey: `choco install ffmpeg`

## Installation Steps

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Discord Token
The bot token is already configured in the `.env` file. Make sure it's valid.

### 3. Bot Permissions
Make sure your bot has the following permissions in Discord Developer Portal:
- Read Messages/View Channels
- Send Messages
- Connect (Voice)
- Speak (Voice)

### 4. Run the Bot
```bash
python bot.py
```

## Usage

Once the bot is running and in your Discord server:

### Discord Commands
- `/help` - Display all available commands
- `/soundboard` - Show an interactive soundboard with buttons (up to 25 sounds where showInButton=true)
- `/update` - Re-sync commands and reload sounds (use if new sounds don't appear in /soundboard)
- `/join` - Bot joins the "Lobby" voice channel and plays test.mp3
- `/play` - Plays test.mp3 (if already in a voice channel)
- `/leave` - Bot leaves the voice channel

### Web Interface (Sound Management)
The bot runs a web server at **http://localhost:5000** where you can:
- **Upload new sounds** (mp3, wav, ogg, flac - max 16MB)
- Set sound **title**, **emoji**, and **showInButton** property
- **View all uploaded sounds**
- **Delete sounds** you no longer need

**Sound Properties:**
- **Title**: Display name for the sound
- **Emoji**: Icon shown with the sound
- **showInButton**: If true, the sound appears in `/soundboard` (max 25 sounds)

**Interactive Soundboard:** Use `/soundboard` to get a message with buttons. Each button plays a different sound! The first 25 sounds with `showInButton=true` will be displayed.

**Note:** After the bot starts, it may take a few seconds for slash commands to appear in Discord.

## Troubleshooting

- **"FFmpeg not found"**: Make sure FFmpeg is installed and in your system PATH
- **Bot can't find "Lobby"**: Make sure you have a voice channel named "Lobby" (case-insensitive)
- **No audio**: Check that the bot has "Speak" permission in the voice channel
- **New sounds don't appear in /soundboard**: Use the `/update` command to re-sync and reload the sounds database
