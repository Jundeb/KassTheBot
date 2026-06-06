import discord
from discord.ext import commands
import asyncio
from asyncio import run_coroutine_threadsafe
from urllib import parse, request
import re
import json
import os
import yt_dlp as youtube_dl

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.is_playing = {}
        self.is_paused = {}
        self.musicQueue = {}
        self.queueIndex = {}

        self.YTDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        self.embedBlue = 0x2c76dd
        self.embedRed = 0xdf1141
        self.embedGreen = 0x0eaa51

        self.vc = {}

        self.VOLUME_FILE = "volume.json"
        self.volumes = self.load_volumes()
    
    # runs once when the bot is ready or becomes online
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            id = int(guild.id)
            self.musicQueue[id] = []
            self.queueIndex[id] = 0
            self.vc[id] = None
            self.is_paused[id] = self.is_playing[id] = False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        id = int(member.guild.id)
        if member.id != self.bot.user.id and before.channel != None and after.channel != before.channel:
            reminingChannelMembers = before.channel.members
            if len(reminingChannelMembers) == 1 and reminingChannelMembers[0].id == self.bot.user.id and self.vc[id].is_connected():
                self.is_playing[id] = self.is_paused[id] = False
                self.musicQueue[id] = []
                self.queueIndex[id] = 0
                await self.vc[id].disconnect()

    def now_playing_embed(self, ctx, song):
        title = song['title']
        link = song['link']
        thumbnail = song['thumbnail']
        author = ctx.author
        avatar = author.display_avatar.url

        embed = discord.Embed(
            title="Now Playing",
            description=f"[{title}]({link})",
            color=self.embedBlue
        )
        embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Song added by: {str(author)}", icon_url=avatar)
        return embed
    
    def added_song_embed(self, ctx, song):
        title = song['title']
        link = song['link']
        thumbnail = song['thumbnail']
        author = ctx.author
        avatar = author.display_avatar.url

        embed = discord.Embed(
            title="Song Added to Queue",
            description=f"[{title}]({link})",
            color=self.embedRed
        )
        embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Song added by: {str(author)}", icon_url=avatar)
        return embed
    
    def removed_song_embed(self, ctx, song):
        title = song['title']
        link = song['link']
        thumbnail = song['thumbnail']
        author = ctx.author
        avatar = author.display_avatar.url

        embed = discord.Embed(
            title="Song Removed from Queue",
            description=f"[{title}]({link})",
            color=self.embedRed
        )
        embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Song removed by: {str(author)}", icon_url=avatar)
        return embed
    
    # ctx contains a ton of info about the message sender and the channel...
    async def join_voice_channel(self, ctx, channel):
        id = int(ctx.guild.id)
        if self.vc[id] == None or not self.vc[id].is_connected():
            self.vc[id] = await channel.connect()

            # if the channel.connect failed
            if self.vc[id] == None:
                await ctx.send("Could not connect to the voice channel.")
                return
        else:
            # if already connected to a channel, move to the new one
            await self.vc[id].move_to(channel)

    def get_youtube_title(self, videoID):
        params = {
            "format": "json", 
            "url": "https://www.youtube.com/watch?v=%s" % videoID
        }
        url = "https://www.youtube.com/oembed"
        query_string = parse.urlencode(params)
        url = url + "?" + query_string
        with request.urlopen(url) as response:
            response_text = response.read()
            data = json.loads(response_text.decode())
            return data['title']

    def search_youtube(self, search):
        queryString = parse.urlencode({'search_query': search})
        htmContent = request.urlopen('http://www.youtube.com/results?' + queryString)
        # first 10 results
        searchResults = re.findall('/watch\?v=(.{11})', htmContent.read().decode())
        return searchResults[0:10]
    
    def extract_youtube(self, url):
        with youtube_dl.YoutubeDL(self.YTDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                # Let yt-dlp pick the best audio format, don't index blindly
                source_url = next(
                    f['url'] for f in info['formats']
                    if f.get('acodec') != 'none' and f.get('url')
                )
            except Exception as e:
                print(f"yt-dlp extraction failed: {e}")
                return False
        return {
            'link': f'https://www.youtube.com/watch?v={url}',
            'thumbnail': f'https://i.ytimg.com/vi/{url}/hqdefault.jpg',
            'source': source_url,
            'title': info['title']
        }
    
    def play_next(self, ctx):
        id = int(ctx.guild.id)
        if not self.is_playing[id]:
            return
        if self.queueIndex[id] + 1 < len(self.musicQueue[id]):
            self.is_playing[id] = True
            self.queueIndex[id] += 1

            song = self.musicQueue[id][self.queueIndex[id]][0]
            message = self.now_playing_embed(ctx, song)
            coro = ctx.send(embed=message)
            fut = run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                fut.result()
            except:
                pass
            
            self.vc[id].play(self.make_source(id, song), after=lambda e: self.play_next(ctx))
        else:
            self.queueIndex[id] += 1
            self.is_playing[id] = False

    async def play_music(self, ctx):
        id = int(ctx.guild.id)
        if self.queueIndex[id] < len(self.musicQueue[id]):
            self.is_playing[id] = True
            self.is_paused[id] = False

            await self.join_voice_channel(ctx, self.musicQueue[id][self.queueIndex[id]][1])

            song = self.musicQueue[id][self.queueIndex[id]][0]
            message = self.now_playing_embed(ctx, song)
            await ctx.send(embed=message)

            # Go to the voice channel then play the song
            self.vc[id].play(
                self.make_source(id, song),
                after=lambda e: print(f"FFmpeg error: {e}") or self.play_next(ctx) if e else self.play_next(ctx)
            )
        else:
            await ctx.send("There are no songs in the queue to be played.")
            self.queueIndex[id] += 1
            # tutorial had is_playing = False, which one is correct?
            self.is_playing[id] = False

    def load_volumes(self):
        if os.path.isfile(self.VOLUME_FILE):
            try:
                with open(self.VOLUME_FILE, "r") as f:
                    return {int(k): v for k, v in json.load(f).items()}
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}

    def save_volumes(self):
        with open(self.VOLUME_FILE, "w") as f:
            json.dump(self.volumes, f)

    def make_source(self, guild_id, song):
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(song['source'], **self.FFMPEG_OPTIONS),
            volume=self.volumes.get(guild_id, 50) / 100
        )

    @commands.command(
        name="pspsps",
        aliases=["j", "join"],
        help="Makes the bot join your voice channel."
    )
    async def join(self, ctx):
        if ctx.author.voice:
            userChannel = ctx.author.voice.channel
            await self.join_voice_channel(ctx, userChannel)
            await ctx.send(f"KassTheBot has joined {userChannel}")
        else:
            await ctx.send("You need to be connected to a voice channel.")

    @commands.command(
        name="tssst",
        aliases=["l", "leave"],
        help="Makes the bot leave the voice channel."
    )
    async def leave(self, ctx):
        # gets server id
        id = int(ctx.guild.id)
        self.is_playing[id] = self.is_paused[id] = False
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        if self.vc[id] != None:
            await ctx.send(f"KassTheBot has left {self.vc[id].channel}")
            await self.vc[id].disconnect()
            self.vc[id] = None

    @commands.command(
        name="purr",
        aliases=["p", "play"],
        help="Plays a song from YouTube."
    )
    async def play(self, ctx, *args):
        search = " ".join(args)
        id = int(ctx.guild.id)
        try:
            userChannel = ctx.author.voice.channel
        except:
            await ctx.send("You must be connected to a voice channel.")
            return
        if not args:
            if len(self.musicQueue[id]) == 0:
                await ctx.send("There are no songs to be played in the queue.")
                return
            elif not self.is_playing[id]:
                if self.musicQueue[id] == None or self.vc[id] == None:
                    await self.play_music(ctx)
                else:
                    self.is_paused[id] = False
                    self.is_playing[id] = True
                    self.vc[id].resume()
        else:
            song = self.extract_youtube(self.search_youtube(search)[0])
            if type(song) == type(True):
                await ctx.send("Could not download the song. Incorrect format, try a different keywords.")
            else:
                self.musicQueue[id].append([song, userChannel])

                if not self.is_playing[id]:
                    await self.play_music(ctx)
                else:
                    message = self.added_song_embed(ctx, song)
                    await ctx.send(embed=message)
    
    @commands.command(
        name="NO",
        aliases=["pa", "stop", "pause"],
        help="Pauses the currently playing song."
    )
    async def pause(self, ctx):
        id = int(ctx.guild.id)
        if not self.vc[id]:
            await ctx.send("I am not connected to a voice channel.")
        elif self.is_playing[id]:
            await ctx.send("Music paused.")
            self.is_playing[id] = False
            self.is_paused[id] = True
            self.vc[id].pause()

    @commands.command(
        name="go on",
        aliases=["re", "resume"],
        help="Resumes the currently paused song."
    )
    async def resume(self, ctx):
        id = int(ctx.guild.id)
        if not self.vc[id]:
            await ctx.send("I am not connected to a voice channel.")
        elif self.is_paused[id]:
            await ctx.send("Music resumed.")
            self.is_playing[id] = True
            self.is_paused[id] = False
            self.vc[id].resume()
        elif self.is_playing[id]:
            await ctx.send("The music is already playing.")
        elif not self.is_playing[id] and not self.is_paused[id]:
            await ctx.send("There is no music to resume.")

    @commands.command(
        name="add",
        aliases=["a"],
        help="Adds a song to the queue."
    )
    async def add(self, ctx, *args):
        search = " ".join(args)
        id = int(ctx.guild.id)
        try:
            userChannel = ctx.author.voice.channel
        except:
            await ctx.send("You must be connected to a voice channel.")
        if not args:
            await ctx.send("You need to specify a song to be added.")
        else:
            song = self.extract_youtube(self.search_youtube(search)[0])
            if type(song) == type(False):
                await ctx.send("Could not download the song. Incorrect format, try a different keywords.")
                return
            else:
                self.musicQueue[ctx.guild.id].append([song, userChannel])
                message = self.added_song_embed(ctx, song)
                await ctx.send(embed=message)
    
    @commands.command(
        name="remove",
        aliases=["rm"],
        help="Removes a song from the queue."
    )
    async def remove(self, ctx):
        id = int(ctx.guild.id)
        if self.musicQueue[id] != []:
            song = self.musicQueue[id][-1][0]
            removeSongEmbed = self.removed_song_embed(ctx, song)
            await ctx.send(embed=removeSongEmbed)
        else:
            await ctx.send("There are no songs in the queue to be removed.")
        self.musicQueue[id] = self.musicQueue[id][:-1]
        if self.musicQueue[id] == []:
            if self.vc[id] != None and self.is_playing[id]:
                self.is_playing[id] = self.is_paused[id] = False
                await self.vc[id].disconnect()
                self.vc[id] = None
            self.queueIndex[id] = 0
        elif self.queueIndex[id] == len(self.musicQueue[id]) and self.vc[id] != None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(ctx)

    @commands.command(
        name="queue",
        aliases=["q", "list"],
        help="Displays the current music queue."
    )
    async def queue(self, ctx):
        id = int(ctx.guild.id)
        returnValue = ""
        if self.musicQueue[id] == []:
            await ctx.send("There are no songs in the queue.")
            return
        
        for i in range(self.queueIndex[id], len(self.musicQueue[id])):
            #start list from the currently playing song
            upNextSongs = len(self.musicQueue[id]) - self.queueIndex[id]
            if i > 5 + upNextSongs:
                break
            returnIndex = i - self.queueIndex[id]
            if returnIndex == 0:
                returnIndex = "Now Playing"
            elif returnIndex == 1:
                returnIndex = "Up Next"
            returnValue += f"{returnIndex} - [{self.musicQueue[id][i][0]['title']}]({self.musicQueue[id][i][0]['link']})\n"

            if returnValue == "":
                await ctx.send("There are no songs in the queue.")
                return
        
        queue = discord.Embed(
            title = "Current Queue",
            description = returnValue,
            color = self.embedGreen
        )
        await ctx.send(embed=queue)
    
    @commands.command(
        name="clear",
        aliases=["c"],
        help="Clears the current music queue."
    )
    async def clear(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] != None and self.is_playing[id]:
            self.is_playing[id] = self.is_paused[id] = False
            self.vc[id].stop()
        if self.musicQueue[id] != []:
            await ctx.send("The music queue has been cleared.")
            self.musicQueue[id] = []
        self.queueIndex[id] = 0
    
    @commands.command(
        name="skip",
        help="Skips the currently playing song."
    )
    async def skip(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] == None:
            await ctx.send("I am not connected to a voice channel.")
        elif self.queueIndex[id] > len(self.musicQueue[id]) - 1:
            await ctx.send("There are no more songs in the queue. Replaying the current song.")
            self.vc[id].pause()
            await self.play_music(ctx)
        elif self.vc[id] != None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] += 1
            await self.play_music(ctx)
    
    @commands.command(
        name="previous",
        aliases=["prev", "pr"],
        help="Plays the previous song in the queue."
    )
    async def previous(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] == None:
            await ctx.send("I am not connected to a voice channel.")
        elif self.queueIndex[id] <= 0:
            await ctx.send("There are no previous songs in the queue. Replaying the current song.")
            self.vc[id].pause()
            await self.play_music(ctx)
        elif self.vc[id] != None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(ctx)
        
    @commands.command(
        name="volume", 
        aliases=["v"], 
        help="Changes the volume (0-100)."
    )
    async def volume(self, ctx, *args):
        id = int(ctx.guild.id)

        if not args:
            await ctx.send(f"Current volume: {self.volumes.get(id, 50)}%")
            return

        try:
            vol = int(args[0])
        except ValueError:
            await ctx.send("Volume must be a number between 0 and 100.")
            return

        if not 0 <= vol <= 100:
            await ctx.send("Volume must be between 0 and 100.")
            return

        self.volumes[id] = vol
        self.save_volumes()

        # Apply to the currently playing source, if any
        if self.vc.get(id) and self.vc[id].source:
            self.vc[id].source.volume = vol / 100

        await ctx.send(f"🔊 Volume set to {vol}%")

