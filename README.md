# yt-dlp proxy

A simple proxy server that uses `yt-dlp` to get direct streamable links from YouTube and other supported websites. Intended for use with the Music Player Daemon, but may work with other software, due to its simplicity.

Currently, the proxy only redirects to the link from `yt-dlp`. Ideally, the metadata would show up in MPD, but so far efforts to inject it in a way that MPD would pick up have failed.

## Summary

Although some ways exist to stream from YouTube, even some using `yt-dlp`, this approach does not require downloading the content first, and enables keeping persistent links to the content in playlists.

## Usage

```bash
$ fastapi start main
```

## API

### GET `/redirect`

Redirects to a direct streamable URL for the given link, takes the following query parameters:

* `url`,
* `stream_type` (optional): Controls which type of stream from `yt-dlp` is used - `video` or `audio`. Defaults to `audio` for MPD (detected from the `User-Agent` header), `video` otherwise.

## Usage sample

Add an entry to the queue:

```
$ mpc add http://localhost:8000/redirect?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

The entry should play, including after saving it to a playlist and loading it later.

Note that it is also possible to add and name the entry by editing the playlist manually:

```
#EXTM3U
#EXTINF:-1,Rick Astley - Never Gonna Give You Up
http://localhost:8000/redirect?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

The way this name is displayed varies between clients, and seems to only work when loading the entire playlist into the queue.
