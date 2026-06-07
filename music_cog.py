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

        self.GUILD_PLAYLISTS_FILE = "guild_playlists.json"
        self.guild_playlists = self.load_guild_playlists()

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
        searchResults = re.findall(r'/watch\?v=(.{11})', htmContent.read().decode())
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
            'video_id': url,
            'link': f'https://www.youtube.com/watch?v={url}',
            'thumbnail': f'https://i.ytimg.com/vi/{url}/hqdefault.jpg',
            'source': source_url,
            'title': info['title']
        }

    def search_and_extract(self, query):
        results = self.search_youtube(query)
        if not results:
            return None
        return self.extract_youtube(results[0]) or None   # collapse False -> None

    def ensure_source(self, song):
        # Saved playlist entries carry no 'source' (those URLs expire), so resolve a
        # fresh one here. Returns True if the song is playable, False otherwise.
        if song.get('source'):
            return True
        fresh = self.extract_youtube(song['video_id'])
        if not fresh:
            return False
        song['source'] = fresh['source']
        return True

    def play_next(self, ctx):
        id = int(ctx.guild.id)
        if not self.is_playing[id]:
            return
        if self.queueIndex[id] + 1 < len(self.musicQueue[id]):
            self.is_playing[id] = True
            self.queueIndex[id] += 1

            song = self.musicQueue[id][self.queueIndex[id]][0]

            if not self.ensure_source(song):
                # couldn't resolve a stream URL; skip this track
                run_coroutine_threadsafe(ctx.send(f"Couldn't load **{song['title']}**, skipping."), self.bot.loop)
                self.play_next(ctx)
                return

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

            # Resolve a fresh stream URL off the event loop (playlist entries have none).
            if not await asyncio.to_thread(self.ensure_source, song):
                await ctx.send(f"Couldn't load **{song['title']}**, skipping.")
                self.queueIndex[id] += 1
                await self.play_music(ctx)
                return

            message = self.now_playing_embed(ctx, song)
            await ctx.send(embed=message)

            # Go to the voice channel then play the song
            self.vc[id].play(
                self.make_source(id, song),
                after=lambda e: print(f"FFmpeg error: {e}") or self.play_next(ctx) if e else self.play_next(ctx)
            )
        else:
            await ctx.send("There are no songs in the queue to be played.")
            self.is_playing[id] = False
            self.queueIndex[id] = len(self.musicQueue[id])

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

    def load_guild_playlists(self):
        if os.path.isfile(self.GUILD_PLAYLISTS_FILE):
            try:
                with open(self.GUILD_PLAYLISTS_FILE, "r") as f:
                    return {int(k): v for k, v in json.load(f).items()}
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}

    def save_guild_playlists(self):
        with open(self.GUILD_PLAYLISTS_FILE, "w") as f:
            json.dump(self.guild_playlists, f)

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
            song = await asyncio.to_thread(self.search_and_extract, search)
            if song is None:
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
        if not ctx.author.voice:
            await ctx.send("You must be connected to a voice channel.")
            return
        userChannel = ctx.author.voice.channel
        if not args:
            await ctx.send("You need to specify a song to be added.")
            return
        song = await asyncio.to_thread(self.search_and_extract, search)
        if song is None:
            await ctx.send("Could not download the song. Incorrect format, try a different keywords.")
            return
        self.musicQueue[id].append([song, userChannel])
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
        elif self.queueIndex[id] + 1 >= len(self.musicQueue[id]):
            await ctx.send("There are no more songs in the queue. Replaying the current song.")
            self.vc[id].pause()
            await self.play_music(ctx)
        else:
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

        if self.vc.get(id) and self.vc[id].source:
            self.vc[id].source.volume = vol / 100

        await ctx.send(f"🔊 Volume set to {vol}%")

    @commands.command(
        name="playlists",
        aliases=["pls"],
        help="Lists all playlists for this server. Usage: `kass playlists`"
    )
    async def playlists(self, ctx):
        id = int(ctx.guild.id)
        playlists = self.guild_playlists.get(id, {})
        if not playlists:
            await ctx.send("There are no saved playlists for this guild.")
            return
        playlist_list = "\n".join(f"{i+1}. {name} ({len(songs)} songs)" for i, (name, songs) in enumerate(playlists.items()))
        embed = discord.Embed(
            title="Saved Playlists",
            description=playlist_list,
            color=self.embedGreen
        )
        await ctx.send(embed=embed)

    @commands.group(
        name="playlist",
        aliases=["pl"],
        invoke_without_command=True,
        help="Manage server playlists. Run alone to list them, or use a subcommand."
    )
    async def playlist(self, ctx):
        await self.playlists(ctx)

    @playlist.command(
        name="create",
        aliases=["plc"],
        help="Creates a new playlist. Usage: `kass playlist create <playlist_name>`"
    )
    async def playlist_create(self, ctx, *args):
        id = int(ctx.guild.id)
        if not args:
            await ctx.send("You must specify a name for the playlist. Usage: `kass playlist create <playlist_name>`")
            return
        playlist_name = " ".join(args)
        if " " in playlist_name:
            await ctx.send("Playlist names cannot contain spaces.")
            return
        if id not in self.guild_playlists:
            self.guild_playlists[id] = {}
        if playlist_name in self.guild_playlists[id]:
            await ctx.send("A playlist with that name already exists.")
            return
        self.guild_playlists[id][playlist_name] = []
        self.save_guild_playlists()
        await ctx.send(f"Playlist '{playlist_name}' created successfully.")

    @playlist.command(
        name="delete",
        aliases=["pld"],
        help="Deletes a playlist. Usage: `kass playlist delete <playlist_name>`"
    )
    async def playlist_delete(self, ctx, *args):
        id = int(ctx.guild.id)
        if not args:
            await ctx.send("You must specify the name of the playlist to delete. Usage: `kass playlist delete <playlist_name>`")
            return
        playlist_name = " ".join(args)
        if id not in self.guild_playlists or playlist_name not in self.guild_playlists[id]:
            await ctx.send("No playlist with that name exists.")
            return
        del self.guild_playlists[id][playlist_name]
        self.save_guild_playlists()
        await ctx.send(f"Playlist '{playlist_name}' deleted successfully.")

    @playlist.command(
        name="show",
        aliases=["plsh"],
        help="Shows the songs in a playlist. Usage: `kass playlist show <playlist_name>`"
    )
    async def playlist_show(self, ctx, *args):
        id = int(ctx.guild.id)
        if not args:
            await ctx.send("You must specify the name of the playlist to show. Usage: `kass playlist show <playlist_name>`")
            return
        playlist_name = " ".join(args)
        if " " in playlist_name:
            await ctx.send("Playlist names cannot contain spaces.")
            return
        if id not in self.guild_playlists or playlist_name not in self.guild_playlists[id]:
            await ctx.send("No playlist with that name exists.")
            return
        songs = self.guild_playlists[id][playlist_name]
        if not songs:
            await ctx.send(f"The playlist '{playlist_name}' is empty.")
            return
        song_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(songs))
        embed = discord.Embed(
            title=f"Playlist: {playlist_name}",
            description=song_list,
            color=self.embedGreen
        )
        await ctx.send(embed=embed)

    @playlist.command(
        name="add",
        aliases=["pla"],
        help="Adds a song to a playlist. Usage: `kass playlist add <playlist_name> <song_name>`"
    )
    async def playlist_add(self, ctx, *args):
        id = int(ctx.guild.id)
        if len(args) < 2:
            await ctx.send("You must specify the playlist name and the song name. Usage: `kass playlist add <playlist_name> <song_name>`")
            return
        playlist_name = args[0]
        if " " in playlist_name:
            await ctx.send("Playlist names cannot contain spaces.")
            return
        song_name = " ".join(args[1:])
        if id not in self.guild_playlists or playlist_name not in self.guild_playlists[id]:
            await ctx.send("No playlist with that name exists.")
            return
        song = await asyncio.to_thread(self.search_and_extract, song_name)
        if song is None:
            await ctx.send("Could not find the song. Try a different name.")
            return
        entry = {k: song[k] for k in ("video_id", "title", "link", "thumbnail")}
        self.guild_playlists[id][playlist_name].append(entry)
        self.save_guild_playlists()
        await ctx.send(f"Song '{song['title']}' added to playlist '{playlist_name}' successfully.")

    @playlist.command(
        name="remove",
        aliases=["plr"],
        help="Removes a song from a playlist. Usage: `kass playlist remove <playlist_name> <song_index>`"
    )
    async def playlist_remove(self, ctx, *args):
        id = int(ctx.guild.id)
        if len(args) < 2:
            await ctx.send("You must specify the playlist name and the song index. Usage: `kass playlist remove <playlist_name> <song_index>`")
            return
        playlist_name = args[0]
        if " " in playlist_name:
            await ctx.send("Playlist names cannot contain spaces.")
            return
        try:
            song_index = int(args[1]) - 1
        except ValueError:
            await ctx.send("Song index must be a number.")
            return
        if id not in self.guild_playlists or playlist_name not in self.guild_playlists[id]:
            await ctx.send("No playlist with that name exists.")
            return
        if song_index < 0 or song_index >= len(self.guild_playlists[id][playlist_name]):
            await ctx.send("Invalid song index.")
            return
        removed_song = self.guild_playlists[id][playlist_name].pop(song_index)
        self.save_guild_playlists()
        await ctx.send(f"Song '{removed_song['title']}' removed from playlist '{playlist_name}' successfully.")

    @playlist.command(
        name="play",
        aliases=["plp"],
        help="Adds all the songs from a playlist to the queue and starts playing. Usage: `kass playlist play <playlist_name>`"
    )
    async def playlist_play(self, ctx, *args):
        id = int(ctx.guild.id)
        if not ctx.author.voice:
            await ctx.send("You must be connected to a voice channel.")
            return
        if not args:
            await ctx.send("You must specify the name of the playlist to play. Usage: `kass playlist play <playlist_name>`")
            return
        playlist_name = " ".join(args)
        if " " in playlist_name:
            await ctx.send("Playlist names cannot contain spaces.")
            return
        if id not in self.guild_playlists or playlist_name not in self.guild_playlists[id]:
            await ctx.send("No playlist with that name exists.")
            return
        songs = self.guild_playlists[id][playlist_name]
        if not songs:
            await ctx.send("The specified playlist is empty.")
            return
        channel = ctx.author.voice.channel
        for song in songs:
            self.musicQueue[id].append([dict(song), channel])

        if not self.is_playing[id]:
            self.queueIndex[id] = 0
            await self.play_music(ctx)
        else:
            await ctx.send(f"Added {len(songs)} songs from playlist '{playlist_name}' to the queue.")

    @playlist.command(
        name="replace",
        aliases=["rp"],
        help="Replaces a song in a playlist. Usage: `kass playlist replace <playlist_name> <song_index> <new_song_name>`"
    )
    async def playlist_replace(self, ctx, *args):
        id = int(ctx.guild.id)
        if len(args) < 3:
            await ctx.send("You must specify the playlist name, the song index, and the new song name. Usage: `kass playlist replace <playlist_name> <song_index> <new_song_name>`")
            return
        playlist_name = args[0]
        if " " in playlist_name:
            await ctx.send("Playlist names cannot contain spaces.")
            return
        try:
            song_index = int(args[1]) - 1
        except ValueError:
            await ctx.send("Song index must be a number.")
            return
        new_song_name = " ".join(args[2:])
        if id not in self.guild_playlists or playlist_name not in self.guild_playlists[id]:
            await ctx.send("No playlist with that name exists.")
            return
        if song_index < 0 or song_index >= len(self.guild_playlists[id][playlist_name]):
            await ctx.send("Invalid song index.")
            return
        new_song = await asyncio.to_thread(self.search_and_extract, new_song_name)
        if new_song is None:
            await ctx.send("Could not find the new song. Try a different name.")
            return
        entry = {k: new_song[k] for k in ("video_id", "title", "link", "thumbnail")}
        self.guild_playlists[id][playlist_name][song_index] = entry
        self.save_guild_playlists()
        await ctx.send(f"Song at index {song_index + 1} in playlist '{playlist_name}' replaced with '{new_song['title']}' successfully.")