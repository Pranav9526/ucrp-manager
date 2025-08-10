
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord import ui, Interaction, TextStyle, Embed, Color
from cogs.ticket_system import TicketPanelView
from cogs.interview import InterviewPanelView
from dotenv import load_dotenv
import os
from discord.ui import View, Button
import datetime
import asyncio
import traceback
import re
import logging
import json
logging.basicConfig(level=logging.ERROR)

# === CONFIG ===
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = 1169251155721846855  # Replace with your server ID
PROOF_CHANNEL_ID = 1393423615432720545  # Channel where proofs will be sent
LOG_CHANNEL_ID = 1395449524570423387 # Channel where logs will be sent
ALLOWED_ROLE_ID = 1346488365608079452  # Role allowed to use forwardproof
SAY_ROLE_ID = 1346488355486961694  # Role allowed to use say commands
ADMIN_LOG_ROLE_ID = 1346488363053482037 # Role allowed to use log commands
TICKET_CHANNEL_PREFIX = "ticket-"
WHITELISTED_ROLE_ID = 1346488379734491196  # 🔁 Replace with actual role ID

WHITELIST_LOG_CHANNEL_ID = 1346488637537386617 # Channel where the embed should be sent
BAN_LOG_CHANNEL_ID = 1346488664917671946
JAIL_LOG_CHANNEL_ID = 1382895763717226516
FC_LOG_CHANNEL_ID = 1377862821924044860
MENTION_ROLE_ID = 1346488379734491196
INTERVIEW_ACCEPTED_ROLE_ID = 1347946934308176013

REVIEW_CHANNEL_ID = 1379753912155770941
REVIEWER_ROLE_ID = 1346488365608079452
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1372059707694645360/1396061147333005343/image.png?ex=6881fcc3&is=6880ab43&hm=ae6f0295e136bc7e1a0619674cb9e8844e87fdee8ebc6a2b688ab4206234168e&"

REJECTED_LOG_CHANNEL_ID = 1379763922994991195
ACCEPTED_LOG_CHANNEL_ID = 1359919316530630918
ACCEPTED_ROLE_ID = 1347946934308176013
PENDING_ROLE_ID = 1346488381500166194
REVIEW_VIDEO_CHANNEL_ID = 1346488640523472958

# Ticket System Configuration
TICKET_CATEGORY_ID = 1356589620141490218  # Open tickets category
CLOSED_TICKET_CATEGORY_ID = 1356590186552758495  # Closed tickets category
STAFF_ROLE_ID = 1346488365608079452  # Server staff role for ticket management

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions(everyone=False, roles=True, users=True))


# Remove default help command to avoid conflict
bot.remove_command("help")

@bot.event
async def on_ready():
    # Initialize ticket system data
    await initialize_ticket_system()

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="UCRP Players"
        )
    )
    # Load cogs manually
    load_cogs = [
        "ticket_system", "poll", "interview", "logs",
        "forward_proof", "say", "sayembed",
        "whitelist", "userinfo", "help_about",
        "dm", "join_dm", "server_status"
    ]
    for cog in load_cogs:
        try:
            await bot.load_extension(f"cogs.{cog}")
            print(f"✅ Loaded {cog} cog")
        except Exception as e:
            print(f"Error loading {cog} cog: {e}")

    # Restore panels from panels.json
    try:
        with open("panels.json") as f:
            panels = json.load(f)

        for panel_type, data in panels.items():
            channel = bot.get_channel(data["channel_id"])
            if channel:
                try:
                    message = await channel.fetch_message(data["message_id"])
                    if panel_type == "ticket_panel":
                        await message.edit(view=TicketPanelView(bot))
                    elif panel_type == "interview_panel":
                        await message.edit(view=InterviewPanelView(bot))
                except Exception as e:
                    print(f"Failed to reattach {panel_type}: {e}")
    except FileNotFoundError:
        print("⚠ panels.json not found — skipping panel restore")

    print(f"✅ Bot ready: {bot.user}")
    # Sync slash commands to your guild
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} slash commands to your server (Guild: {GUILD_ID})")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")

    print(f"Bot is ready: {bot.user}")


async def initialize_ticket_system():
    """Initialize ticket system data files"""
    os.makedirs('data', exist_ok=True)

    # Initialize tickets.json
    if not os.path.exists('data/tickets.json'):
        with open('data/tickets.json', 'w') as f:
            json.dump({}, f)

    # Initialize config.json
    if not os.path.exists('data/config.json'):
        with open('data/config.json', 'w') as f:
            json.dump({
                "ticket_category": TICKET_CATEGORY_ID,
                "closed_category": CLOSED_TICKET_CATEGORY_ID,
                "ticket_counter": 0
            }, f, indent=2)

# -------------WATCHING UCRP------------

#----------Date TIme Handler ----------
def format_datetime(dt: datetime.datetime):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# --------- Emoji Say Handler ---------
def resolve_emojis(message: discord.Message) -> str:
    content = message.content

    # Match <a:name:id> or <:name:id>
    custom_emoji_pattern = r'<a?:\w+:\d+>'
    matches = re.findall(custom_emoji_pattern, content)

    for match in matches:
        content = content.replace(match, match)  # Leave it as-is so it renders in embed

    return content

# -------- force re-sync ---------
@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await ctx.send(f"✅ Synced {len(synced)} slash commands to this server.")
    except Exception as e:
        await ctx.send(f"❌ Sync failed.\n`{e}`")

# ----------- error handling ---------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        await ctx.send("❌ An unexpected error occurred.")
        print(f"[ERROR] {error}")

# ------------ SERVER WHITELIST ----------
@bot.event
async def on_guild_join(guild):
    if guild.id != YOUR_SERVER_ID:
        await guild.leave()

# ------------- Auto Delete Messages in Trolls and insta ---------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Channel IDs to monitor
    monitored_channels = [1346488677441732700, 1346488679035834460]
    # Role ID that can bypass this (staff role with /sayembed access)
    staff_role_id = 1346488355486961694

    if message.channel.id in monitored_channels:
        # Check if user has staff role
        is_staff = any(role.id == staff_role_id for role in message.author.roles)

        # If not staff and message has no attachments (text-only message)
        if not is_staff and len(message.attachments) == 0:
            await message.delete()

            # Reminder embed
            embed = discord.Embed(
                description=f"❌ {message.author.mention}, please don’t chat in this channel. It's only for in-game media posts.",
                color=discord.Color.red()
            )

            # Send reminder and delete after 5 seconds
            warning_msg = await message.channel.send(embed=embed)
            await asyncio.sleep(5)
            await warning_msg.delete()

    await bot.process_commands(message)

# -------- Keep Alive & Run --------
bot.run(TOKEN)
