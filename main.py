import discord
from discord.ext import commands
from music_cog import music_cog
from help_cog import help_cog

intents = discord.Intents.default()
intents.message_content = True

class Kass(commands.Bot):
    async def setup_hook(self):
        self.remove_command("help")
        await self.add_cog(music_cog(self))
        await self.add_cog(help_cog(self))

bot = Kass(command_prefix="kass ", intents=intents)

with open("token.txt", "r") as file:
    token = file.readline().strip()

bot.run(token)