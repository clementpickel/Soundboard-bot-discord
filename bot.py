import discord
from discord import app_commands
from discord.ui import View, Button
from discord.ext import tasks
import os
import json
import threading
import asyncio
import audioop
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Set up bot with intents (no privileged intents needed)
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True

# Flask app setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'assets'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac'}

SOUNDS_FILE = 'sounds.json'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_sounds():
    """Load sounds from JSON file"""
    try:
        with open(SOUNDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"sounds": []}

def save_sounds(data):
    """Save sounds to JSON file"""
    with open(SOUNDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Flask routes
@app.route('/')
def index():
    """Main upload page"""
    return render_template('upload.html')

@app.route('/api/sounds', methods=['GET'])
def get_sounds():
    """Get all sounds"""
    data = load_sounds()
    return jsonify(data)

@app.route('/api/sounds', methods=['POST'])
def upload_sound():
    """Upload a new sound"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: mp3, wav, ogg, flac'}), 400
    
    # Get metadata
    title = request.form.get('title', '')
    emoji = request.form.get('emoji', '🔊')
    show_in_button = request.form.get('showInButton', 'false').lower() == 'true'
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    # Save file
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # Update sounds.json
    data = load_sounds()
    sound_id = filename.rsplit('.', 1)[0]  # Remove extension for ID
    
    # Check if sound already exists
    existing = next((s for s in data['sounds'] if s['id'] == sound_id), None)
    if existing:
        existing['title'] = title
        existing['emoji'] = emoji
        existing['showInButton'] = show_in_button
    else:
        data['sounds'].append({
            'id': sound_id,
            'title': title,
            'emoji': emoji,
            'filename': filename,
            'showInButton': show_in_button
        })
    
    save_sounds(data)
    
    return jsonify({'success': True, 'message': 'Sound uploaded successfully'})

@app.route('/api/sounds/<sound_id>', methods=['DELETE'])
def delete_sound(sound_id):
    """Delete a sound"""
    data = load_sounds()
    sound = next((s for s in data['sounds'] if s['id'] == sound_id), None)
    
    if not sound:
        return jsonify({'error': 'Sound not found'}), 404
    
    # Delete file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], sound['filename'])
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Remove from JSON
    data['sounds'] = [s for s in data['sounds'] if s['id'] != sound_id]
    save_sounds(data)
    
    return jsonify({'success': True, 'message': 'Sound deleted successfully'})

def run_flask():
    """Run Flask app in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# Audio Mixer for simultaneous playback
class AudioMixer(discord.AudioSource):
    """Mix multiple audio sources together for simultaneous playback"""
    
    def __init__(self):
        self.sources = []
        self.lock = threading.Lock()
    
    def add_source(self, source):
        """Add an audio source to the mixer"""
        with self.lock:
            self.sources.append(source)
    
    def remove_source(self, source):
        """Remove an audio source from the mixer"""
        with self.lock:
            if source in self.sources:
                self.sources.remove(source)
    
    def read(self):
        """Read and mix audio from all sources"""
        with self.lock:
            if not self.sources:
                return b''
            
            # Read from all sources
            frames = []
            sources_to_remove = []
            
            for source in self.sources:
                try:
                    data = source.read()
                    if data:
                        frames.append(data)
                    else:
                        # Source is exhausted
                        sources_to_remove.append(source)
                        if hasattr(source, 'cleanup'):
                            source.cleanup()
                except Exception as e:
                    print(f"Error reading from source: {e}")
                    sources_to_remove.append(source)
            
            # Remove exhausted sources
            for source in sources_to_remove:
                self.sources.remove(source)
            
            if not frames:
                return b''
            
            # Mix all frames together
            if len(frames) == 1:
                return frames[0]
            
            # Average mixing
            mixed = frames[0]
            for frame in frames[1:]:
                # Ensure both frames are the same length
                min_len = min(len(mixed), len(frame))
                mixed = audioop.add(mixed[:min_len], frame[:min_len], 2)
            
            # Reduce volume to prevent clipping (divide by number of sources)
            if len(frames) > 1:
                mixed = audioop.mul(mixed, 2, 1.0 / len(frames))
            
            return mixed
    
    def cleanup(self):
        """Clean up all sources"""
        with self.lock:
            for source in self.sources:
                if hasattr(source, 'cleanup'):
                    try:
                        source.cleanup()
                    except:
                        pass
            self.sources.clear()
    
    def is_opus(self):
        return False

# Store mixers per guild
guild_mixers = {}

# Store last activity time per guild
guild_last_activity = {}

# Store channel name per guild
guild_channel_names = {}

def get_or_create_mixer(guild_id):
    """Get or create a mixer for a guild"""
    if guild_id not in guild_mixers:
        guild_mixers[guild_id] = AudioMixer()
    return guild_mixers[guild_id]

def update_activity(guild_id):
    """Update the last activity time for a guild"""
    guild_last_activity[guild_id] = datetime.now()

# Discord bot setup
class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        # OPTION 1: Sync to specific guild(s) - INSTANT updates (recommended for testing)
        # Replace YOUR_GUILD_ID with your server's ID (right-click server -> Copy ID)
        guild = discord.Object(id=858374770557976606)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        
        # OPTION 2: Global sync - takes up to 1 hour to update
        await self.tree.sync()

bot = MyBot()

@tasks.loop(minutes=1)
async def check_inactive_guilds():
    """Check for inactive guilds and disconnect if idle for 10 minutes"""
    now = datetime.now()
    guilds_to_disconnect = []
    
    for voice_client in bot.voice_clients:
        guild_id = voice_client.guild.id
        
        # Check if guild has activity tracking
        if guild_id in guild_last_activity:
            last_activity = guild_last_activity[guild_id]
            idle_time = now - last_activity
            
            # If idle for more than 10 minutes, mark for disconnection
            if idle_time > timedelta(minutes=10):
                guilds_to_disconnect.append((voice_client, guild_id))
    
    # Disconnect from inactive guilds
    for voice_client, guild_id in guilds_to_disconnect:
        try:
            # Clean up the mixer
            if guild_id in guild_mixers:
                guild_mixers[guild_id].cleanup()
                del guild_mixers[guild_id]
            
            # Remove activity tracking
            if guild_id in guild_last_activity:
                del guild_last_activity[guild_id]
            
            await voice_client.disconnect()
            print(f"Auto-disconnected from guild {guild_id} due to 10 minutes of inactivity")
        except Exception as e:
            print(f"Error disconnecting from guild {guild_id}: {e}")

@check_inactive_guilds.before_loop
async def before_check_inactive_guilds():
    """Wait for the bot to be ready before starting the loop"""
    await bot.wait_until_ready()

# Dynamic Soundboard button view
class DynamicSoundboardView(View):
    def __init__(self, sounds):
        super().__init__(timeout=None)
        
        # Add buttons for up to 25 sounds (Discord limit is 25 buttons per message)
        for sound in sounds[:25]:
            button = Button(
                label=f"{sound['emoji']} {sound['title']}",
                style=discord.ButtonStyle.primary,
                custom_id=f"play_{sound['id']}"
            )
            button.callback = self.create_callback(sound)
            self.add_item(button)
    
    def create_callback(self, sound):
        """Create a callback function for each button"""
        async def callback(interaction: discord.Interaction):
            channel_name = guild_channel_names.get(interaction.guild.id, "Lobby")
            lobby_channel = discord.utils.get(interaction.guild.voice_channels, name=channel_name)
            
            if lobby_channel is None:
                await interaction.response.send_message(f"Could not find a voice channel named '{channel_name}'", ephemeral=True)
                return
            
            # Get the voice client for this guild
            voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
            
            # Connect to the voice channel if not already connected
            if voice_client is None:
                voice_client = await lobby_channel.connect()
            elif voice_client.channel != lobby_channel:
                await voice_client.move_to(lobby_channel)
            
            # Wait for connection to be ready
            if not voice_client.is_connected():
                await interaction.response.send_message(f"⏳ Connecting to voice... Please try again in a moment.", ephemeral=True)
                return
            
            # Play the sound
            audio_path = f"assets/{sound['filename']}"
            if not os.path.exists(audio_path):
                await interaction.response.send_message(f"❌ Sound file not found: {sound['filename']}", ephemeral=True)
                return
            
            # Update activity tracking
            update_activity(interaction.guild.id)
            
            # Get or create mixer for this guild
            mixer = get_or_create_mixer(interaction.guild.id)
            
            # Add audio source to mixer
            audio_source = discord.FFmpegPCMAudio(audio_path)
            mixer.add_source(audio_source)
            
            # Start playing mixer if not already playing
            if not voice_client.is_playing():
                voice_client.play(mixer, after=lambda e: print(f'Mixer stopped: {e}' if e else 'Mixer stopped'))
            
            await interaction.response.send_message(f"🎵 Playing {sound['emoji']} {sound['title']}!", ephemeral=True)
        
        return callback

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    print('Commands synced!')
    print('Web interface available at: https://soundboard.clementpickel.fr/')
    
    # Start the inactive guild checker
    if not check_inactive_guilds.is_running():
        check_inactive_guilds.start()
        print('Auto-leave after 10 minutes of inactivity: ENABLED')

@bot.tree.command(name='join', description='Join a voice channel and play test.mp3')
@app_commands.describe(channel_name='Voice channel name (default: Lobby)')
async def join_lobby(interaction: discord.Interaction, channel_name: str = "Lobby"):
    """Join a voice channel and play test.mp3"""
    
    guild_id = interaction.guild.id
    guild_channel_names[guild_id] = channel_name
    
    lobby_channel = discord.utils.get(interaction.guild.voice_channels, name=channel_name)
    
    if lobby_channel is None:
        await interaction.response.send_message(f"Could not find a voice channel named '{channel_name}'")
        return
    
    # Get the voice client for this guild
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    
    # Connect to the voice channel
    if voice_client is None:
        voice_client = await lobby_channel.connect()
        await interaction.response.send_message(f"Joined {lobby_channel.name}!")
    else:
        await voice_client.move_to(lobby_channel)
        await interaction.response.send_message(f"Moved to {lobby_channel.name}!")
    
    # Update activity tracking
    update_activity(interaction.guild.id)
    
    # Get or create mixer for this guild
    mixer = get_or_create_mixer(interaction.guild.id)
    
    # Add audio source to mixer
    audio_source = discord.FFmpegPCMAudio('assets/test.mp3')
    mixer.add_source(audio_source)
    
    # Start playing mixer if not already playing
    if not voice_client.is_playing():
        voice_client.play(mixer, after=lambda e: print(f'Mixer stopped: {e}' if e else 'Mixer stopped'))

@bot.tree.command(name='leave', description='Disconnect from the voice channel')
async def leave_voice(interaction: discord.Interaction):
    """Disconnect from the voice channel"""
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    
    if voice_client:
        # Clean up the mixer
        if interaction.guild.id in guild_mixers:
            guild_mixers[interaction.guild.id].cleanup()
            del guild_mixers[interaction.guild.id]
        
        await voice_client.disconnect()
        await interaction.response.send_message("Disconnected from voice channel!")
    else:
        await interaction.response.send_message("I'm not in a voice channel!")

@bot.tree.command(name='stop', description='Stop all currently playing sounds')
async def stop_sounds(interaction: discord.Interaction):
    """Stop all sounds that are currently playing"""
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    
    if voice_client is None:
        await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
        return
    
    # Update activity tracking
    update_activity(interaction.guild.id)
    
    # Clean up the mixer and create a new one
    if interaction.guild.id in guild_mixers:
        guild_mixers[interaction.guild.id].cleanup()
        del guild_mixers[interaction.guild.id]
    
    # Stop the voice client
    if voice_client.is_playing():
        voice_client.stop()
    
    await interaction.response.send_message("🛑 Stopped all sounds!", ephemeral=True)

@bot.tree.command(name='play', description='Play test.mp3')
async def play_sound(interaction: discord.Interaction):
    """Play the sound if already in a voice channel"""
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    
    if voice_client is None:
        await interaction.response.send_message("I'm not in a voice channel! Use /join first")
        return
    
    # Update activity tracking
    update_activity(interaction.guild.id)
    
    # Get or create mixer for this guild
    mixer = get_or_create_mixer(interaction.guild.id)
    
    # Add audio source to mixer
    audio_source = discord.FFmpegPCMAudio('assets/test.mp3')
    mixer.add_source(audio_source)
    
    # Start playing mixer if not already playing
    if not voice_client.is_playing():
        voice_client.play(mixer, after=lambda e: print(f'Mixer stopped: {e}' if e else 'Mixer stopped'))
    
    await interaction.response.send_message("Playing test.mp3!")

@bot.tree.command(name='help', description='Show available commands')
async def help_command(interaction: discord.Interaction):
    """Display help information"""
    embed = discord.Embed(
        title="🎵 Soundboard Bot Help",
        description="Here are all available commands:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="/join",
        value="Join a voice channel and play test.mp3 (default: Lobby)",
        inline=False
    )
    embed.add_field(
        name="/play",
        value="Play test.mp3 (if bot is already in a voice channel)",
        inline=False
    )
    embed.add_field(
        name="/stop",
        value="Stop all currently playing sounds",
        inline=False
    )
    embed.add_field(
        name="/leave",
        value="Disconnect from the voice channel",
        inline=False
    )
    embed.add_field(
        name="/soundboard",
        value="Display an interactive soundboard with buttons (up to 25 sounds) - sounds can play simultaneously!",
        inline=False
    )
    embed.add_field(
        name="/help",
        value="Show this help message",
        inline=False
    )
    
    embed.add_field(
        name="/update",
        value="Re-sync commands and reload sounds (use if /soundboard doesn't show new sounds)",
        inline=False
    )
    
    embed.add_field(
        name="🌐 Web Interface",
        value="Upload and manage sounds at: https://soundboard.clementpickel.fr/",
        inline=False
    )
    
    embed.set_footer(text="Click the buttons to play sounds! Multiple sounds can play at once!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='update', description='Re-sync commands and reload sounds database')
async def update_command(interaction: discord.Interaction):
    """Re-sync commands to update soundboard"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Reload sounds from file
        data = load_sounds()
        button_sounds = [s for s in data['sounds'] if s.get('showInButton', False)][:25]
        
        # Re-sync commands to the guild
        guild = discord.Object(id=interaction.guild_id)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        
        embed = discord.Embed(
            title="✅ Update Complete",
            description="Commands have been re-synced!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📊 Soundboard Status",
            value=f"**{len(button_sounds)}** sounds will appear in `/soundboard`\n"
                  f"**{len(data['sounds'])}** total sounds in database",
            inline=False
        )
        
        if button_sounds:
            sound_list = "\n".join([f"{s['emoji']} {s['title']}" for s in button_sounds[:5]])
            if len(button_sounds) > 5:
                sound_list += f"\n... and {len(button_sounds) - 5} more"
            
            embed.add_field(
                name="🔊 Available Sounds",
                value=sound_list,
                inline=False
            )
        
        embed.set_footer(text="Try /soundboard now to see updated buttons!")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error during update: {str(e)}",
            ephemeral=True
        )
        print(f"Error in update command: {e}")

@bot.tree.command(name='soundboard', description='Display interactive soundboard')
@app_commands.describe(page='Page number (1, 2, 3...)')
async def soundboard_command(interaction: discord.Interaction, page: int = 1):
    """Display soundboard with buttons"""

    # Load sounds from JSON
    data = load_sounds()

    # Filter sounds with showInButton=true
    all_button_sounds = [s for s in data['sounds'] if s.get('showInButton', False)]
    total_sounds = len(all_button_sounds)
    total_pages = max(1, (total_sounds + 24) // 25)

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * 25
    end_idx = start_idx + 25
    button_sounds = all_button_sounds[start_idx:end_idx]

    if not button_sounds:
        await interaction.response.send_message(
            f"❌ No sounds on page {page}. Upload sounds at https://soundboard.clementpickel.fr/",
            ephemeral=True
        )
        return

    page_info = f"Page {page} of {total_pages}" if total_pages > 1 else f"{total_sounds} sounds"

    embed = discord.Embed(
        title="🎵 Soundboard",
        description=f"Click a button to play a sound!\nThe bot will join the configured voice channel automatically.\n\n**{page_info}**",
        color=discord.Color.green()
    )

    sound_list = "\n".join([f"{s['emoji']} **{s['title']}**" for s in button_sounds[:10]])
    if len(button_sounds) > 10:
        sound_list += f"\n... and {len(button_sounds) - 10} more!"

    embed.add_field(
        name="📁 Available Sounds",
        value=sound_list,
        inline=False
    )

    if total_pages > 1:
        embed.set_footer(text=f"Use /soundboard {{1-{total_pages}}} to see more pages | Upload at https://soundboard.clementpickel.fr/")
    else:
        embed.set_footer(text="Upload more sounds at https://soundboard.clementpickel.fr/")

    view = DynamicSoundboardView(button_sounds)
    await interaction.response.send_message(embed=embed, view=view)

# Run the bot
if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Starting Discord bot...")
    print("Web interface will be available at https://soundboard.clementpickel.fr/")
    
    # Run the Discord bot
    bot.run(TOKEN)

