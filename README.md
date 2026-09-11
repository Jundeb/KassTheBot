# Kass the Bot

A Discord music bot (prefix: `kass `) that plays audio from YouTube, with per-guild queues and saved playlists.

## Requirements

- Python 3.9+
- `ffmpeg` (audio decoding for voice playback)
- A Discord bot token with the **Message Content** intent enabled in the [Discord Developer Portal](https://discord.com/developers/applications)

## Setup on Raspberry Pi

### 1. Get the code

```bash
git clone <this-repo-url> KassTheBot
cd KassTheBot
```

### 2. Run the installer

```bash
chmod +x install.sh
./install.sh
```

This one script does everything, and is safe to re-run later (e.g. after `git pull`):

- installs `ffmpeg` and Python dependencies (`pip install -r requirements.txt --break-system-packages` — Raspberry Pi OS blocks plain system-wide `pip install`, this is the standard override for a Pi dedicated to one bot)
- prompts for your Discord bot token and saves it to `token.txt` (skipped if that file already exists, so re-running won't ask again or overwrite it)
- writes and enables `kassthebot.service`, a systemd service that starts the bot on boot and restarts it if it crashes
- writes and enables `kassthebot-update.timer`, which restarts the bot weekly; the service's `ExecStartPre` re-checks `yt-dlp` for updates on every restart, so the bot self-updates on that same schedule

That's the whole setup — once `install.sh` finishes, there's nothing left to do manually, including keeping `yt-dlp` current (see below).

**Your bot token needs a home.** Get one from the [Discord Developer Portal](https://discord.com/developers/applications) (create an app → Bot → Reset Token) before running the installer, or have it ready when prompted. **Never commit `token.txt`** — it's already in `.gitignore`, but if it's ever tracked, treat the token as compromised and regenerate it.

Useful commands after install:

```bash
sudo systemctl status kassthebot          # check it's running
journalctl -u kassthebot -f               # tail logs live
systemctl list-timers kassthebot-update.timer   # confirm the weekly auto-update is scheduled
```

## Why yt-dlp needs to stay current

YouTube frequently changes things on its end, and `yt-dlp` ships fixes for it often — an outdated `yt-dlp` is the most common reason the bot says "Now Playing" but stays silent (logs show `HTTP error 403 Forbidden`). `install.sh` sets up automatic weekly updates (see above) so this shouldn't come up, but if you ever need to force it immediately:

```bash
sudo systemctl restart kassthebot
```

(This works because `ExecStartPre` on `kassthebot.service` re-checks yt-dlp on every restart, not just the scheduled ones.)

## Commands

All commands are prefixed with `kass `, e.g. `kass play never gonna give you up`.

| Command | Aliases | Description |
|---|---|---|
| `help` | `h`, `commands` | Shows all commands and their descriptions |
| `join` | `j`, `pspsps` | Joins your voice channel |
| `leave` | `l`, `tssst` | Leaves the voice channel |
| `play <query>` | `p`, `purr` | Plays a song from YouTube, or resumes/starts the queue if called with no query |
| `pause` | `pa`, `stop`, `NO` | Pauses the current song |
| `resume` | `re`, `go on` | Resumes a paused song |
| `add <query>` | `a` | Adds a song to the queue |
| `remove` | `rm` | Removes the last song in the queue |
| `queue` | `q`, `list` | Shows the current queue |
| `clear` | `c` | Clears the queue |
| `skip` | | Skips to the next song |
| `previous` | `prev`, `pr` | Plays the previous song |
| `volume <0-100>` | `v` | Gets or sets playback volume (persisted per-guild) |
| `playlists` | `pls` | Lists saved playlists for the server |
| `playlist create <name>` | `pl plc` | Creates a playlist |
| `playlist delete <name>` | `pl pld` | Deletes a playlist |
| `playlist show <name>` | `pl plsh` | Lists songs in a playlist |
| `playlist add <name> <query>` | `pl pla` | Adds a song to a playlist |
| `playlist remove <name> <index>` | `pl plr` | Removes a song from a playlist |
| `playlist replace <name> <index> <query>` | `pl rp` | Replaces a song in a playlist |
| `playlist play <name>` | `pl plp` | Queues and plays every song in a playlist |

Playlist names cannot contain spaces.
