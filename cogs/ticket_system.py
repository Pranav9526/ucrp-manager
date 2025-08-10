import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
from utils.ticket_manager import TicketManager
from views.ticket_views import TicketPanelView, TicketControlView

logger = logging.getLogger(__name__)

class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_manager = TicketManager()

    @app_commands.command(name="ticket", description="Send a ticket panel to a channel")
    @app_commands.describe(channel="The channel to send the ticket panel to")
    @app_commands.guilds(1169251155721846855)  # Your guild ID for instant syncing
    async def ticket_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Send a ticket panel to the specified channel"""

        # Permission check
        if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "❌ You need `Manage Channels` permission to use this command!",
                ephemeral=True
            )
            return

        # Get guild icon if available
        guild_icon = interaction.guild.icon.url if interaction.guild.icon else None

        # Modern styled embed
        embed = discord.Embed(
            title="<a:trusted:1369558398382772266> Need Assistance?",
            description=(
                "Welcome to the **Support Center**!\n"
                "Our team is here to help you with any issues, questions, or concerns.\n\n"
                "<a:emoji_87:1353936822102659072> **How It Works**\n"
                "• Click the button below to create a private ticket\n"
                "• Explain your problem in detail\n"
                "• Wait for staff to assist you\n"
            ),
            color=discord.Color.from_rgb(14, 225, 234)
        )

        # Add thumbnail & footer with server branding
        if guild_icon:
            embed.set_thumbnail(url=guild_icon)
            embed.set_footer(text=f"{interaction.guild.name} • Support System", icon_url=guild_icon)
        else:
            embed.set_footer(text=f"{interaction.guild.name} • Support System")

        # Ticket panel button view
        view = TicketPanelView(self.ticket_manager)

        try:
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ Ticket panel has been sent to {channel.mention}!",
                ephemeral=True
            )
            logger.info(f"Ticket panel sent to {channel.name} by {interaction.user}")

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to send messages in that channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error sending ticket panel: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while sending the ticket panel!",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_ready(self):
        """Re-add views when bot restarts"""
        self.bot.add_view(TicketPanelView(self.ticket_manager))
        logger.info("Ticket panel views re-added")


async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
