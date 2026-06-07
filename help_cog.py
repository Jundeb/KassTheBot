import discord
from discord.ext import commands

class help_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embedOrange = 0xeab148
    
    @commands.Cog.listener()
    async def on_ready(self):
        sendToChannels = []
        for guild in self.bot.guilds:
            channel = guild.text_channels[0]
            sendToChannels.append(channel)
        helloEmbed = discord.Embed(
            title = "Hello, I'm Kass!",
            description = "I'm a music bot created by Karvaton Kassi. You can type **`'kass'`** followed by a command. Use `kass help` to see my commands.",
            color = self.embedOrange
        )
        for channel in sendToChannels:
            await channel.send(embed=helloEmbed)
    
    @commands.command(
        name="help",
        aliases=["h", "commands"],
        help="Shows all the commands and their descriptions."
    )
    async def help(self, ctx):
        cogs = [self.bot.get_cog("help_cog"), self.bot.get_cog("music_cog")]
        commands_list = [c for cog in cogs if cog for c in cog.get_commands()]

        desc = "**`kass <command>`** - Provides a description of all commands or a longer description of an input command.\n\n"
        for command in commands_list:
            desc += f"**`kass {command.name}`** - {command.help}\n"
            if isinstance(command, commands.Group):
                for sub in command.commands:
                    desc += f"\u2003**`kass {command.name} {sub.name}`** - {sub.help}\n"

        await ctx.send(embed=discord.Embed(title="Kass Commands", description=desc, color=self.embedOrange))