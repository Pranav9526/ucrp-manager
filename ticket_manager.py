import discord
import json
import logging
from datetime import datetime
from utils.transcript_generator import TranscriptGenerator

logger = logging.getLogger(__name__)

class TicketManager:
    def __init__(self):
        self.transcript_generator = TranscriptGenerator()
        
    def load_config(self):
        """Load configuration from file"""
        try:
            with open('data/config.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {
                "ticket_category": 1392114253103759401,
                "closed_category": 1392114561590493324,
                "ticket_counter": 0
            }
    
    def save_config(self, config):
        """Save configuration to file"""
        try:
            with open('data/config.json', 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def load_tickets(self):
        """Load tickets from file"""
        try:
            with open('data/tickets.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tickets: {e}")
            return {}
    
    def save_tickets(self, tickets):
        """Save tickets to file"""
        try:
            with open('data/tickets.json', 'w') as f:
                json.dump(tickets, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving tickets: {e}")
    
    async def create_ticket(self, guild: discord.Guild, user: discord.Member, reason: str = None):
        """Create a new ticket channel"""
        try:
            # Load configuration
            config = self.load_config()
            tickets = self.load_tickets()
            
            # Check if user already has an open ticket
            user_tickets = [t for t in tickets.values() if t.get('user_id') == user.id and t.get('status') == 'open']
            if user_tickets:
                return None, "You already have an open ticket!"
            
            # Get ticket category
            category = guild.get_channel(config['ticket_category'])
            if not category or not isinstance(category, discord.CategoryChannel):
                return None, "Ticket category not found!"
            
            # Increment ticket counter
            config['ticket_counter'] += 1
            ticket_number = config['ticket_counter']
            
            # Create ticket channel with username (not display name)
            # Clean username for channel name (remove spaces, special chars)
            clean_username = ''.join(c for c in user.name if c.isalnum() or c in '-_').lower()
            if not clean_username:
                clean_username = f"user{user.id}"
            channel_name = f"ticket-{clean_username}"
            
            # Set up permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True
                )
            }
            
            # Add staff role permissions
            staff_role = guild.get_role(1346488365608079452)  # Staff role ID
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True
                )
            
            # Create the channel
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Support ticket for {user.display_name} | Ticket #{ticket_number:04d}"
            )
            
            # Save ticket data
            tickets[str(channel.id)] = {
                'ticket_number': ticket_number,
                'user_id': user.id,
                'user_name': str(user),
                'channel_id': channel.id,
                'status': 'open',
                'created_at': datetime.now().isoformat(),
                'reason': reason,
                'added_users': []
            }
            
            self.save_config(config)
            self.save_tickets(tickets)
            
            logger.info(f"Created ticket #{ticket_number:04d} for {user} in {channel.name}")
            return channel, None
            
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            return None, f"An error occurred while creating the ticket: {str(e)}"
    
    async def add_user_to_ticket(self, channel: discord.TextChannel, user: discord.Member, added_by: discord.Member):
        """Add a user to a ticket"""
        try:
            tickets = self.load_tickets()
            ticket_data = tickets.get(str(channel.id))
            
            if not ticket_data or ticket_data.get('status') != 'open':
                return False, "This is not an active ticket channel!"
            
            # Check if user is already in the ticket
            if user.id in ticket_data.get('added_users', []):
                return False, f"{user.mention} is already added to this ticket!"
            
            # Add permissions for the user
            await channel.set_permissions(
                user,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
            )
            
            # Update ticket data
            if 'added_users' not in ticket_data:
                ticket_data['added_users'] = []
            ticket_data['added_users'].append(user.id)
            
            tickets[str(channel.id)] = ticket_data
            self.save_tickets(tickets)
            
            logger.info(f"Added {user} to ticket {channel.name} by {added_by}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error adding user to ticket: {e}")
            return False, f"An error occurred: {str(e)}"
    
    async def close_ticket(self, channel: discord.TextChannel, closed_by: discord.Member):
        """Close a ticket and move it to closed category"""
        try:
            config = self.load_config()
            tickets = self.load_tickets()
            ticket_data = tickets.get(str(channel.id))
            
            if not ticket_data:
                return False, "This is not a ticket channel!"
            
            if ticket_data.get('status') == 'closed':
                return False, "This ticket is already closed!"
            
            # Generate transcript
            transcript_file = await self.transcript_generator.generate_transcript(channel)
            
            # Get closed category
            closed_category = channel.guild.get_channel(config['closed_category'])
            if not closed_category or not isinstance(closed_category, discord.CategoryChannel):
                return False, "Closed tickets category not found!"
            
            # Move channel to closed category
            await channel.edit(category=closed_category)
            
            # Update channel name
            new_name = f"closed-{channel.name}"
            await channel.edit(name=new_name)
            
            # Remove permissions for ticket creator and added users
            ticket_owner = channel.guild.get_member(ticket_data['user_id'])
            if ticket_owner:
                await channel.set_permissions(ticket_owner, read_messages=False)
            
            for user_id in ticket_data.get('added_users', []):
                user = channel.guild.get_member(user_id)
                if user:
                    await channel.set_permissions(user, read_messages=False)
            
            # Update ticket data
            ticket_data['status'] = 'closed'
            ticket_data['closed_at'] = datetime.now().isoformat()
            ticket_data['closed_by'] = str(closed_by)
            ticket_data['transcript_file'] = transcript_file
            
            tickets[str(channel.id)] = ticket_data
            self.save_tickets(tickets)
            
            logger.info(f"Closed ticket {channel.name} by {closed_by}")
            return True, transcript_file
            
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
            return False, f"An error occurred: {str(e)}"
    
    async def delete_ticket(self, channel: discord.TextChannel, deleted_by: discord.Member):
        """Delete a ticket channel"""
        try:
            tickets = self.load_tickets()
            ticket_data = tickets.get(str(channel.id))
            
            if not ticket_data:
                return False, "This is not a ticket channel!", None
            
            # Generate transcript if not already generated
            transcript_file = ticket_data.get('transcript_file')
            if not transcript_file:
                transcript_file = await self.transcript_generator.generate_transcript(channel)
            
            # Get ticket owner info
            ticket_owner = channel.guild.get_member(ticket_data['user_id'])
            
            # Log to deletion log channel
            log_channel = channel.guild.get_channel(1395449524570423387)
            if log_channel and transcript_file:
                try:
                    log_embed = discord.Embed(
                        title="🗑️ Ticket Deleted",
                        description=f"Ticket `{channel.name}` has been deleted",
                        color=0xff6b6b,
                        timestamp=datetime.now()
                    )
                    log_embed.add_field(
                        name="📋 Ticket Details",
                        value=f"**Ticket Owner:** {ticket_owner.mention if ticket_owner else 'Unknown User'}\n**Deleted By:** {deleted_by.mention}\n**Ticket ID:** {ticket_data.get('ticket_id', 'Unknown')}",
                        inline=False
                    )
                    log_embed.add_field(
                        name="📝 Original Reason",
                        value=ticket_data.get('reason', 'No reason provided')[:1000],
                        inline=False
                    )
                    
                    with open(transcript_file, 'rb') as f:
                        file = discord.File(f, filename=f"transcript-{channel.name}.html")
                        await log_channel.send(embed=log_embed, file=file)
                except Exception as e:
                    logger.error(f"Failed to log ticket deletion: {e}")
            
            # Send transcript to ticket owner if possible
            if ticket_owner and transcript_file:
                try:
                    embed = discord.Embed(
                        title="🗂️ Ticket Transcript",
                        description=f"Your ticket `{channel.name}` has been deleted. Here's the transcript:",
                        color=0xff6b6b
                    )
                    with open(transcript_file, 'rb') as f:
                        file = discord.File(f, filename=f"transcript-{channel.name}.html")
                        await ticket_owner.send(embed=embed, file=file)
                except:
                    pass  # Ignore if unable to DM user
            
            # Remove ticket from data
            del tickets[str(channel.id)]
            self.save_tickets(tickets)
            
            # Delete the channel
            await channel.delete()
            
            logger.info(f"Deleted ticket {channel.name} by {deleted_by}")
            return True, None, transcript_file
            
        except Exception as e:
            logger.error(f"Error deleting ticket: {e}")
            return False, f"An error occurred: {str(e)}", None
    
    def get_ticket_info(self, channel_id: int):
        """Get ticket information"""
        tickets = self.load_tickets()
        return tickets.get(str(channel_id))
    
    async def remove_user_from_ticket(self, channel: discord.TextChannel, user_to_remove: discord.Member, remover: discord.Member):
        """Remove a user from a ticket channel"""
        try:
            # Get ticket info
            tickets = self.load_tickets()
            ticket_info = tickets.get(str(channel.id))
            
            if not ticket_info:
                return False, "This is not a ticket channel!"
            
            # Check if trying to remove the ticket owner
            if user_to_remove.id == ticket_info.get('user_id'):
                return False, "Cannot remove the ticket owner from their own ticket!"
            
            # Check if user has access to the channel
            permissions = channel.permissions_for(user_to_remove)
            if not permissions.read_messages:
                return False, "User doesn't have access to this ticket!"
            
            # Remove user's permissions
            await channel.set_permissions(user_to_remove, overwrite=None)
            
            # Remove from added_users list if present
            if 'added_users' in ticket_info and user_to_remove.id in ticket_info['added_users']:
                ticket_info['added_users'].remove(user_to_remove.id)
                tickets[str(channel.id)] = ticket_info
                self.save_tickets(tickets)
            
            logger.info(f"User {user_to_remove} removed from ticket {channel.name} by {remover}")
            return True, "User removed successfully"
            
        except Exception as e:
            logger.error(f"Error removing user from ticket: {e}")
            return False, f"An error occurred: {str(e)}"
    
    async def reopen_ticket(self, channel: discord.TextChannel, reopener: discord.Member):
        """Reopen a closed ticket"""
        try:
            # Load configuration
            config = self.load_config()
            tickets = self.load_tickets()
            
            # Get ticket info
            ticket_info = tickets.get(str(channel.id))
            if not ticket_info:
                return False, "This is not a ticket channel!"
            
            if ticket_info.get('status') != 'closed':
                return False, "This ticket is not closed!"
            
            # Get categories
            open_category = channel.guild.get_channel(config['ticket_category'])
            if not open_category or not isinstance(open_category, discord.CategoryChannel):
                return False, "Open ticket category not found!"
            
            # Move channel back to open category
            await channel.edit(category=open_category)
            
            # Remove "closed-" prefix from channel name if present
            new_name = channel.name
            if new_name.startswith('closed-'):
                new_name = new_name[7:]  # Remove "closed-" prefix
                await channel.edit(name=new_name)
            
            # Get the original ticket owner
            ticket_owner = channel.guild.get_member(ticket_info['user_id'])
            if ticket_owner:
                # Restore owner's permissions
                await channel.set_permissions(
                    ticket_owner,
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True
                )
            
            # Restore permissions for added users
            for user_id in ticket_info.get('added_users', []):
                user = channel.guild.get_member(user_id)
                if user:
                    await channel.set_permissions(
                        user,
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True
                    )
            
            # Update ticket status
            ticket_info['status'] = 'open'
            ticket_info['reopened_at'] = datetime.now().isoformat()
            ticket_info['reopened_by'] = reopener.id
            tickets[str(channel.id)] = ticket_info
            
            # Save tickets data
            self.save_tickets(tickets)
            
            logger.info(f"Ticket {channel.name} reopened by {reopener}")
            return True, "Ticket reopened successfully"
            
        except Exception as e:
            logger.error(f"Error reopening ticket: {e}")
            return False, f"An error occurred: {str(e)}"
