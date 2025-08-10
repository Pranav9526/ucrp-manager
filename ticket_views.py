import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

# Staff role ID for permissions
STAFF_ROLE_ID = 1346488365608079452

class TicketPanelView(discord.ui.View):
    def __init__(self, ticket_manager):
        super().__init__(timeout=None)
        self.ticket_manager = ticket_manager
    
    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.green,
        emoji="🎫",
        custom_id="create_ticket"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle ticket creation button"""
        
        # Create modal for ticket reason
        modal = TicketReasonModal(self.ticket_manager)
        await interaction.response.send_modal(modal)

class TicketReasonModal(discord.ui.Modal):
    def __init__(self, ticket_manager):
        super().__init__(title="Create Support Ticket")
        self.ticket_manager = ticket_manager
        
        self.reason_input = discord.ui.TextInput(
            label="What do you need help with?",
            placeholder="Please describe your issue or question...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer(ephemeral=True)
        
        reason = self.reason_input.value
        
        # Create the ticket
        channel, error = await self.ticket_manager.create_ticket(
            interaction.guild,
            interaction.user,
            reason
        )
        
        if error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return
        
        # Send welcome message to the ticket channel
        embed = discord.Embed(
            title="🎫 Ticket Created",
            description=f"Hello {interaction.user.mention}!\n\nYour support ticket has been created.",
            color=0x00ff88
        )
        embed.add_field(name="📝 Issue", value=reason, inline=False)
        embed.add_field(
            name="📋 What happens next?",
            value="• Our support team will be with you shortly\n• Please provide any additional details\n• Use the buttons below to manage your ticket",
            inline=False
        )
        embed.set_footer(text=f"Ticket created by {interaction.user}")
        
        # Create control view
        control_view = TicketControlView(self.ticket_manager)
        
        await channel.send(f"{interaction.user.mention}", embed=embed, view=control_view)
        
        # Notify user
        await interaction.followup.send(
            f"✅ Your ticket has been created! {channel.mention}",
            ephemeral=True
        )
        
        logger.info(f"Ticket created for {interaction.user} in {channel.name}")

class TicketControlView(discord.ui.View):
    def __init__(self, ticket_manager):
        super().__init__(timeout=None)
        self.ticket_manager = ticket_manager
    
    def _is_staff_member(self, member: discord.Member) -> bool:
        """Check if user is a staff member"""
        return any(role.id == STAFF_ROLE_ID for role in member.roles)
    
    @discord.ui.button(
        label="Add User",
        style=discord.ButtonStyle.secondary,
        emoji="➕",
        custom_id="add_user"
    )
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a user to the ticket"""
        
        # Check permissions (ticket owner or staff)
        ticket_info = self.ticket_manager.get_ticket_info(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
            return
        
        # Check permissions (staff only for adding users)
        if not self._is_staff_member(interaction.user):
            await interaction.response.send_message("❌ Only server staff can add users to tickets!", ephemeral=True)
            return
        
        # Show user input modal
        modal = UserActionModal(self.ticket_manager, "add")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket"""
        
        # Check permissions
        ticket_info = self.ticket_manager.get_ticket_info(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
            return
        
        is_ticket_owner = interaction.user.id == ticket_info.get('user_id')
        is_staff = self._is_staff_member(interaction.user)
        
        if not (is_ticket_owner or is_staff):
            await interaction.response.send_message("❌ Only the ticket owner or server staff can close this ticket!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Close the ticket
        success, result = await self.ticket_manager.close_ticket(interaction.channel, interaction.user)
        
        if not success:
            await interaction.followup.send(f"❌ {result}")
            return
        
        # Send closure message
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}",
            color=0xff6b6b
        )
        embed.add_field(
            name="📋 What happened?",
            value="• Ticket moved to closed category\n• User access removed\n• Transcript generated",
            inline=False
        )
        embed.set_footer(text="Ticket System")
        
        # Create delete view
        delete_view = DeleteTicketView(self.ticket_manager)
        
        await interaction.followup.send(embed=embed, view=delete_view)
        
        logger.info(f"Ticket {interaction.channel.name} closed by {interaction.user}")
    
    @discord.ui.button(
        label="Remove User",
        style=discord.ButtonStyle.secondary,
        emoji="➖",
        custom_id="remove_user"
    )
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a user from the ticket"""
        
        # Check permissions (staff only for removing users)
        if not self._is_staff_member(interaction.user):
            await interaction.response.send_message("❌ Only server staff can remove users from tickets!", ephemeral=True)
            return
        
        ticket_info = self.ticket_manager.get_ticket_info(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
            return
        
        # Show user input modal for removal
        modal = UserActionModal(self.ticket_manager, "remove")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Delete Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="delete_ticket"
    )
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the ticket"""
        
        # Check permissions (staff only)
        if not self._is_staff_member(interaction.user):
            await interaction.response.send_message("❌ Only server staff can delete tickets!", ephemeral=True)
            return
        
        # Show confirmation modal
        modal = DeleteConfirmationModal(self.ticket_manager)
        await interaction.response.send_modal(modal)



class DeleteConfirmationModal(discord.ui.Modal):
    def __init__(self, ticket_manager):
        super().__init__(title="Delete Ticket Confirmation")
        self.ticket_manager = ticket_manager
        
        self.confirmation_input = discord.ui.TextInput(
            label="Type 'DELETE' to confirm",
            placeholder="This action cannot be undone!",
            max_length=10,
            required=True
        )
        self.add_item(self.confirmation_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmation_input.value.upper() != "DELETE":
            await interaction.response.send_message("❌ Confirmation failed. Deletion cancelled.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Delete the ticket
        success, error, transcript = await self.ticket_manager.delete_ticket(
            interaction.channel,
            interaction.user
        )
        
        if not success:
            await interaction.followup.send(f"❌ {error}")
            return
        
        # Send deletion message (won't be seen since channel is deleted)
        try:
            await interaction.followup.send("🗑️ Ticket will be deleted in 3 seconds...")
        except:
            pass

class UserActionModal(discord.ui.Modal):
    def __init__(self, ticket_manager, action_type):
        title = "Add User to Ticket" if action_type == "add" else "Remove User from Ticket"
        super().__init__(title=title)
        self.ticket_manager = ticket_manager
        self.action_type = action_type
        
        self.user_input = discord.ui.TextInput(
            label="User ID, mention, or username",
            placeholder="Enter @username, user ID, or display name",
            max_length=100,
            required=True
        )
        self.add_item(self.user_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        user_input = self.user_input.value.strip()
        
        # Try to find the user
        user = await self._find_user(interaction.guild, user_input)
        
        if not user:
            await interaction.followup.send("❌ User not found! Please provide a valid user ID, mention, or username.", ephemeral=True)
            return
        
        if self.action_type == "add":
            # Add user to ticket
            success, error = await self.ticket_manager.add_user_to_ticket(
                interaction.channel,
                user,
                interaction.user
            )
            
            if not success:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            
            # Send success message
            embed = discord.Embed(
                title="➕ User Added",
                description=f"{user.mention} has been added to this ticket by {interaction.user.mention}",
                color=0x00ff88
            )
            
            await interaction.channel.send(embed=embed)
            await interaction.followup.send(f"✅ Successfully added {user.mention} to the ticket!", ephemeral=True)
            
        elif self.action_type == "remove":
            # Remove user from ticket
            success, error = await self.ticket_manager.remove_user_from_ticket(
                interaction.channel,
                user,
                interaction.user
            )
            
            if not success:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            
            # Send success message
            embed = discord.Embed(
                title="➖ User Removed",
                description=f"{user.mention} has been removed from this ticket by {interaction.user.mention}",
                color=0xff6b6b
            )
            
            await interaction.channel.send(embed=embed)
            await interaction.followup.send(f"✅ Successfully removed {user.mention} from the ticket!", ephemeral=True)
    
    async def _find_user(self, guild, user_input):
        """Find a user by various input methods"""
        user = None
        
        # Try mention format
        if user_input.startswith('<@') and user_input.endswith('>'):
            user_id = user_input[2:-1]
            if user_id.startswith('!'):
                user_id = user_id[1:]
            try:
                user = guild.get_member(int(user_id))
            except ValueError:
                pass
        
        # Try user ID
        if not user:
            try:
                user = guild.get_member(int(user_input))
            except ValueError:
                pass
        
        # Try display name or username (case insensitive)
        if not user:
            user_input_lower = user_input.lower()
            for member in guild.members:
                if (member.display_name.lower() == user_input_lower or 
                    member.name.lower() == user_input_lower or
                    user_input_lower in member.display_name.lower()):
                    user = member
                    break
        
        return user

class DeleteTicketView(discord.ui.View):
    def __init__(self, ticket_manager):
        super().__init__(timeout=300)  # 5 minute timeout
        self.ticket_manager = ticket_manager
    
    def _is_staff_member(self, member: discord.Member) -> bool:
        """Check if user is a staff member"""
        return any(role.id == STAFF_ROLE_ID for role in member.roles)
    
    @discord.ui.button(
        label="Reopen Ticket",
        style=discord.ButtonStyle.success,
        emoji="🔓"
    )
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reopen the closed ticket"""
        
        # Check permissions (staff only)
        if not self._is_staff_member(interaction.user):
            await interaction.response.send_message("❌ Only server staff can reopen tickets!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Reopen the ticket
        success, error = await self.ticket_manager.reopen_ticket(interaction.channel, interaction.user)
        
        if not success:
            await interaction.followup.send(f"❌ {error}")
            return
        
        # Send reopen message
        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=f"This ticket has been reopened by {interaction.user.mention}",
            color=0x00ff88
        )
        embed.add_field(
            name="📋 What happened?",
            value="• Ticket moved back to open category\n• User access restored\n• Ticket is now active again",
            inline=False
        )
        embed.set_footer(text="Ticket System")
        
        # Create control view for reopened ticket
        control_view = TicketControlView(self.ticket_manager)
        
        await interaction.followup.send(embed=embed, view=control_view)
        
        logger.info(f"Ticket {interaction.channel.name} reopened by {interaction.user}")
    
    @discord.ui.button(
        label="Delete Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the closed ticket"""
        
        # Check permissions (staff only)
        if not self._is_staff_member(interaction.user):
            await interaction.response.send_message("❌ Only server staff can delete tickets!", ephemeral=True)
            return
        
        # Show confirmation modal
        modal = DeleteConfirmationModal(self.ticket_manager)
        await interaction.response.send_modal(modal)
