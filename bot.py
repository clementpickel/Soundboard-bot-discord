import discord
from discord import app_commands
from discord.ui import View, Button
import os
import json
import threading
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
            # Find the "Lobby" voice channel
            lobby_channel = None
            for channel in interaction.guild.voice_channels:
                if channel.name.lower() == 'lobby':
                    lobby_channel = channel
                    break
            
            if lobby_channel is None:
                await interaction.response.send_message("Could not find a voice channel named 'Lobby'", ephemeral=True)
                return
            
            # Get the voice client for this guild
            voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
            
            # Connect to the voice channel if not already connected
            if voice_client is None:
                voice_client = await lobby_channel.connect()
            elif voice_client.channel != lobby_channel:
                await voice_client.move_to(lobby_channel)
            
            # Play the sound
            audio_path = f"assets/{sound['filename']}"
            if not os.path.exists(audio_path):
                await interaction.response.send_message(f"❌ Sound file not found: {sound['filename']}", ephemeral=True)
                return
            
            audio_source = discord.FFmpegPCMAudio(audio_path)
            
            if voice_client.is_playing():
                voice_client.stop()
            
            voice_client.play(audio_source, after=lambda e: print(f'Finished playing {sound["title"]}: {e}' if e else f'Played {sound["title"]} successfully'))
            await interaction.response.send_message(f"🎵 Playing {sound['emoji']} {sound['title']}!", ephemeral=True)
        
        return callback

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    print('Commands synced!')
    print('Web interface available at: http://localhost:5000')

@bot.tree.command(name='join', description='Join the Lobby voice channel and play test.mp3')
async def join_lobby(interaction: discord.Interaction):
    """Join the Lobby voice channel and play test.mp3"""
    
    # Find the "Lobby" voice channel
    lobby_channel = None
    for channel in interaction.guild.voice_channels:
        if channel.name.lower() == 'lobby':
            lobby_channel = channel
            break
    
    if lobby_channel is None:
        await interaction.response.send_message("Could not find a voice channel named 'Lobby'")
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
    
    # Play the sound
    audio_source = discord.FFmpegPCMAudio('assets/test.mp3')
    
    if voice_client.is_playing():
        voice_client.stop()
    
    voice_client.play(audio_source, after=lambda e: print(f'Finished playing: {e}' if e else 'Sound played successfully'))

@bot.tree.command(name='leave', description='Disconnect from the voice channel')
async def leave_voice(interaction: discord.Interaction):
    """Disconnect from the voice channel"""
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    
    if voice_client:
        await voice_client.disconnect()
        await interaction.response.send_message("Disconnected from voice channel!")
    else:
        await interaction.response.send_message("I'm not in a voice channel!")

@bot.tree.command(name='play', description='Play test.mp3')
async def play_sound(interaction: discord.Interaction):
    """Play the sound if already in a voice channel"""
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    
    if voice_client is None:
        await interaction.response.send_message("I'm not in a voice channel! Use /join first")
        return
    
    audio_source = discord.FFmpegPCMAudio('assets/test.mp3')
    
    if voice_client.is_playing():
        voice_client.stop()
    
    voice_client.play(audio_source, after=lambda e: print(f'Finished playing: {e}' if e else 'Sound played successfully'))
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
        value="Join the Lobby voice channel and play test.mp3",
        inline=False
    )
    embed.add_field(
        name="/play",
        value="Play test.mp3 (if bot is already in a voice channel)",
        inline=False
    )
    embed.add_field(
        name="/leave",
        value="Disconnect from the voice channel",
        inline=False
    )
    embed.add_field(
        name="/soundboard",
        value="Display an interactive soundboard with buttons (up to 25 sounds)",
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
        value="Upload and manage sounds at: http://localhost:5000",
        inline=False
    )
    
    embed.set_footer(text="Click the buttons to play sounds!")
    
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
async def soundboard_command(interaction: discord.Interaction):
    """Display soundboard with buttons"""
    
    # Load sounds from JSON
    data = load_sounds()
    
    # Filter sounds with showInButton=true and limit to 25
    button_sounds = [s for s in data['sounds'] if s.get('showInButton', False)][:25]
    
    if not button_sounds:
        await interaction.response.send_message(
            "❌ No sounds available in the soundboard. Upload sounds at http://localhost:5000",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🎵 Soundboard",
        description=f"Click a button to play a sound!\nThe bot will join the **Lobby** voice channel automatically.\n\n**{len(button_sounds)} sounds available**",
        color=discord.Color.green()
    )
    
    # List sounds
    sound_list = "\n".join([f"{s['emoji']} **{s['title']}**" for s in button_sounds[:10]])
    if len(button_sounds) > 10:
        sound_list += f"\n... and {len(button_sounds) - 10} more!"
    
    embed.add_field(
        name="📁 Available Sounds",
        value=sound_list,
        inline=False
    )
    
    embed.set_footer(text="Upload more sounds at http://localhost:5000")
    
    view = DynamicSoundboardView(button_sounds)
    await interaction.response.send_message(embed=embed, view=view)

# Run the bot
if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Starting Discord bot...")
    print("Web interface will be available at http://localhost:5000")
    
    # Run the Discord bot
    bot.run(TOKEN)

