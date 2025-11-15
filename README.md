# Circlify — Telegram round-video bot

This project converts user-uploaded videos into circular video notes (video_note) suitable for Telegram.

## Features
- Accepts mp4/mov videos (up to 60 seconds)
- Crops center square, scales to 480x480, encodes fast for speed
- Sends result as `video_note` (Telegram displays it round)
- Best-effort reaction attempt when user sends video
- Auto-cleanup of temporary files
- Concurrency limit to avoid overloading host

## Deploy (Render.com)
1. Create GitHub repo and push project files.
2. Create a new **Web Service** on Render and connect the repository.
3. Make sure `render.yaml` exists in repo root. It installs `ffmpeg` during build.
4. Add environment variable `BOT_TOKEN` with your bot token.
5. Deploy.

## Running locally / Termux
- Install system ffmpeg (apt / pkg)
- Create virtualenv, install requirements: `pip install -r requirements.txt`
- Set `BOT_TOKEN` env var
- Run `python3 main.py`

## Notes
- I will pick compatible library versions in `requirements.txt` to avoid compatibility issues.
- If your Telegram client or Bot API version doesn't support message reactions by bots, reaction attempts will be silently ignored.
