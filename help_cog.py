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
        helpCog = self.bot.get_cog("help_cog")
        musicCog = self.bot.get_cog("music_cog")
        commands = helpCog.get_commands() + musicCog.get_commands()

        commandDescription = "**`kass <command>`** - Provides a description of all commands or a longer description of an input command.\n\n"
        for command in commands:
            message = command.help
            commandDescription += f"**`kass {command.name}`** - {message}\n"
        commandsEmbed = discord.Embed(
            title = "Kass Commands",
            description = commandDescription,
            color = self.embedOrange
        )
        await ctx.send(embed=commandsEmbed)