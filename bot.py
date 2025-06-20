import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
import asyncio
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_CHANNEL_ID = 1385247248429875385
ADMIN_CHANNEL_ID = 1385453468231270522
PURGE_CHANNEL_IDS = [
    1385247248429875385,
    1385299936199053383
]

ABUSE_KEYWORDS = [
    "gandu", "chutiya", "madarchod", "bhosdike", "mc", "bc",
    "sale", "behen", "fuck", "shit", "nude", "loda", "gaand",
    "fight", "kill", "rape", "slut", "bitch", "abuse"
]

user_warnings = {}

@bot.event
async def on_ready():
    print(f'✅ Bot is online as {bot.user}')
    purge_task.start()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        await welcome_channel.send(f"🎉 Welcome to the server, {member.mention}!")

    admin_channel = guild.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        embed = discord.Embed(
            title="👤 New Member Joined",
            description=f"**Username:** {member.name}#{member.discriminator}\n"
                        f"**ID:** {member.id}\n"
                        f"**Account Created:** {member.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            color=discord.Color.green()
        )
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        await admin_channel.send(embed=embed)

@tasks.loop(hours=24)
async def purge_task():
    now = datetime.now()
    target = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now > target:
        target += timedelta(days=1)
    wait_seconds = (target - now).total_seconds()
    print(f"⏳ Waiting {int(wait_seconds)} seconds until next purge at 12 AM...")
    await asyncio.sleep(wait_seconds)

    print("🧹 Starting daily purge...")
    for channel_id in PURGE_CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            try:
                await channel.purge(limit=None)
                await channel.send("🧹 Chat cleared automatically at 12:00 AM.")
                print(f"✅ Cleared messages in: {channel.name}")
            except Exception as e:
                print(f"❌ Error clearing {channel.name}: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    for word in ABUSE_KEYWORDS:
        if word in content:
            await message.delete()
            await warn_user(message.author, message.guild, word)
            return

    await bot.process_commands(message)

async def warn_user(user, guild, keyword):
    reason = f"Abusive language detected"
    user_id = user.id
    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
    warning_count = user_warnings[user_id]

    admin_channel = guild.get_channel(ADMIN_CHANNEL_ID)
    if warning_count < 3:
        if admin_channel:
            await admin_channel.send(
                f"⚠️ {user.mention} received warning #{warning_count}.\n**Reason:** {reason}"
            )
        try:
            await user.send(f"⚠️ You received warning #{warning_count} for inappropriate language.")
        except:
            pass
        print(f"⚠️ Warning {warning_count} for {user}")
    else:
        await temp_timeout_user(user, guild, f"{reason} (3rd warning)")
        if admin_channel:
            await admin_channel.send(f"⛔ {user.mention}: Temporarily muted for 15 mins after 3 warnings.")
        user_warnings[user_id] = 0

async def temp_timeout_user(user, guild, reason):
    try:
        duration = timedelta(minutes=15)
        await user.timeout(duration, reason=reason)
        print(f"🔇 Timeout applied to {user} for: {reason}")
    except discord.Forbidden:
        print(f"❌ No permission to timeout {user}")
    except Exception as e:
        print(f"❌ Error during timeout: {e}")

@bot.command(name="tempban")
@commands.has_permissions(moderate_members=True)
async def tempban(ctx, *, identifier):
    guild = ctx.guild
    member = None

    if ctx.message.mentions:
        member = ctx.message.mentions[0]
    else:
        for m in guild.members:
            if str(m) == identifier or m.name == identifier:
                member = m
                break
        if not member and identifier.isdigit():
            member = guild.get_member(int(identifier))

    if not member:
        await ctx.send("❌ User not found.")
        return

    try:
        duration = timedelta(minutes=15)
        reason = "Manual tempban issued by admin"
        await member.timeout(duration, reason=reason)
        await ctx.send(f"⛔ {member.mention} has been muted for 15 minutes.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to timeout this user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="unban")
@commands.has_permissions(moderate_members=True)
async def unban(ctx, *, identifier):
    guild = ctx.guild
    member = None

    if ctx.message.mentions:
        member = ctx.message.mentions[0]
    else:
        for m in guild.members:
            if str(m) == identifier or m.name == identifier:
                member = m
                break
        if not member and identifier.isdigit():
            member = guild.get_member(int(identifier))

    if not member:
        await ctx.send("❌ User not found.")
        return

    try:
        await member.edit(timed_out_until=None)
        await ctx.send(f"✅ {member.mention} has been unmuted.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unban this user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ---------------------------------- CLEAR BUTTONS ----------------------------------

class ClearChannelButton(Button):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(label=f"Clear {channel.name}", style=discord.ButtonStyle.red)
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
            return

        try:
            await self.channel.purge(limit=None)
            await self.channel.send("🧹 Chat cleared by admin.")
            await interaction.response.send_message(f"✅ Cleared {self.channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to clear {self.channel.name}", ephemeral=True)

class ChannelClearView(View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.add_item(ClearChannelButton(channel))

@bot.command(name="clearbutton")
@commands.has_permissions(manage_messages=True)
async def clearbutton(ctx, channel: discord.TextChannel):
    await ctx.send(f"🧼 Press button to clear {channel.mention}", view=ChannelClearView(channel))

@bot.command(name="clearallchannels")
@commands.has_permissions(manage_messages=True)
async def clearall(ctx):
    for cid in PURGE_CHANNEL_IDS:
        channel = bot.get_channel(cid)
        if channel and isinstance(channel, discord.TextChannel):
            try:
                await channel.purge(limit=None)
                await channel.send("🧹 Chat cleared by admin.")
            except Exception as e:
                print(f"❌ Error clearing {channel.name}: {e}")
    await ctx.send("✅ All purge channels cleared.")

# ---------------------------------- SLASH COMMANDS ----------------------------------

@bot.tree.command(name="commands", description="Show admin command list")
async def show_admin_commands(interaction: discord.Interaction):
    if interaction.channel.id != ADMIN_CHANNEL_ID:
        await interaction.response.send_message("❌ Only usable in admin panel.", ephemeral=True)
        return

    embed = discord.Embed(title="🛠 Admin Command List", color=discord.Color.blurple())
    embed.add_field(name="!tempban @user", value="Temporarily mute user (15 min)", inline=False)
    embed.add_field(name="!unban @user", value="Unmute timed-out user", inline=False)
    embed.add_field(name="!clearbutton #channel", value="Show clear button for channel", inline=False)
    embed.add_field(name="!clearallchannels", value="Clear all purge channels", inline=False)
    embed.add_field(name="/commands", value="Show this command list", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------------------------- START BOT ----------------------------------

bot.run("MTM4NTQzNzQzMzEyMTczODgwNA.GIa_Ur.LFUgjr8iiA69NHbOpHHpB9R2b0Amalm5ZXekt0")
