import discord
import html
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TranscriptGenerator:
    def __init__(self):
        self.transcript_dir = "data/transcripts"
        os.makedirs(self.transcript_dir, exist_ok=True)
    
    async def generate_transcript(self, channel: discord.TextChannel):
        """Generate an HTML transcript of the channel"""
        try:
            # Fetch all messages from the channel
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                messages.append(message)
            
            # Generate HTML content
            html_content = self._generate_html(channel, messages)
            
            # Save to file
            filename = f"transcript-{channel.name}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            filepath = os.path.join(self.transcript_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Generated transcript for {channel.name}: {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating transcript: {e}")
            return None
    
    def _generate_html(self, channel: discord.TextChannel, messages):
        """Generate HTML content for the transcript"""
        
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcript - {channel_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #36393f;
            color: #dcddde;
            margin: 0;
            padding: 20px;
        }}
        .header {{
            background-color: #2f3136;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .channel-info {{
            font-size: 24px;
            font-weight: bold;
            color: #7289da;
        }}
        .transcript-info {{
            color: #b9bbbe;
            margin-top: 10px;
        }}
        .message {{
            display: flex;
            padding: 10px 0;
            border-bottom: 1px solid #2f3136;
        }}
        .message:hover {{
            background-color: #32353b;
        }}
        .avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin-right: 16px;
            background-color: #7289da;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            flex-shrink: 0;
        }}
        .message-content {{
            flex: 1;
        }}
        .message-header {{
            display: flex;
            align-items: center;
            margin-bottom: 4px;
        }}
        .username {{
            font-weight: 600;
            color: #ffffff;
            margin-right: 8px;
        }}
        .timestamp {{
            font-size: 12px;
            color: #72767d;
        }}
        .message-text {{
            color: #dcddde;
            line-height: 1.4;
            word-wrap: break-word;
        }}
        .embed {{
            border-left: 4px solid #7289da;
            background-color: #2f3136;
            margin: 8px 0;
            padding: 16px;
            border-radius: 0 4px 4px 0;
        }}
        .embed-title {{
            color: #ffffff;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .embed-description {{
            color: #dcddde;
        }}
        .attachment {{
            background-color: #2f3136;
            padding: 8px;
            border-radius: 4px;
            margin: 4px 0;
            color: #7289da;
        }}
        .system-message {{
            background-color: #2f3136;
            padding: 8px 16px;
            border-radius: 4px;
            margin: 8px 0;
            font-style: italic;
            color: #b9bbbe;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="channel-info">#{channel_name}</div>
        <div class="transcript-info">
            Transcript generated on {timestamp}<br>
            {message_count} messages
        </div>
    </div>
    <div class="messages">
        {messages_html}
    </div>
</body>
</html>
        """
        
        messages_html = ""
        
        for message in messages:
            # Handle system messages
            if message.type != discord.MessageType.default:
                if message.type == discord.MessageType.new_member:
                    messages_html += f'<div class="system-message">📥 {html.escape(message.author.display_name)} joined the server</div>'
                elif message.type == discord.MessageType.pins_add:
                    messages_html += f'<div class="system-message">📌 {html.escape(message.author.display_name)} pinned a message</div>'
                continue
            
            # Get user avatar initials
            avatar_text = message.author.display_name[0].upper() if message.author.display_name else "?"
            
            # Format timestamp
            timestamp = message.created_at.strftime("%m/%d/%Y %I:%M %p")
            
            # Escape HTML in message content
            content = html.escape(message.content) if message.content else ""
            
            # Handle mentions
            content = self._process_mentions(content, message)
            
            # Handle embeds
            embeds_html = ""
            for embed in message.embeds:
                embed_html = '<div class="embed">'
                if embed.title:
                    embed_html += f'<div class="embed-title">{html.escape(embed.title)}</div>'
                if embed.description:
                    embed_html += f'<div class="embed-description">{html.escape(embed.description)}</div>'
                embed_html += '</div>'
                embeds_html += embed_html
            
            # Handle attachments
            attachments_html = ""
            for attachment in message.attachments:
                attachments_html += f'<div class="attachment">📎 {html.escape(attachment.filename)}</div>'
            
            # Build message HTML
            message_html = f"""
            <div class="message">
                <div class="avatar">{avatar_text}</div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="username">{html.escape(message.author.display_name)}</span>
                        <span class="timestamp">{timestamp}</span>
                    </div>
                    <div class="message-text">{content}</div>
                    {embeds_html}
                    {attachments_html}
                </div>
            </div>
            """
            
            messages_html += message_html
        
        # Fill in the template
        return html_template.format(
            channel_name=html.escape(channel.name),
            timestamp=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            message_count=len(messages),
            messages_html=messages_html
        )
    
    def _process_mentions(self, content: str, message: discord.Message):
        """Process Discord mentions in message content"""
        # This is a simplified version - in a full implementation,
        # you would want to properly parse and replace Discord mentions
        return content
