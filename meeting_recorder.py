"""
Alfred's Media Control — Spotify integration.
Full playback control via Spotify Premium API.
"""
import json
import os
import re
import spotipy
from spotipy.oauth2 import SpotifyOAuth

CONFIG_FILE = os.path.expanduser("~/spotify_config.json")
CACHE_FILE = os.path.expanduser("~/.alfred_spotify_cache")
SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "user-library-read "
    "playlist-read-private "
    "playlist-read-collaborative"
)

_sp = None


def get_spotify():
    """Get authenticated Spotify client."""
    global _sp
    if _sp:
        return _sp

    if not os.path.exists(CONFIG_FILE):
        return None

    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    auth = SpotifyOAuth(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        scope=SCOPE,
        cache_path=CACHE_FILE,
        open_browser=True
    )

    _sp = spotipy.Spotify(auth_manager=auth)
    return _sp


def play_search(query, search_type="track"):
    """Search for and play a track, artist, album, or playlist."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured, Sir."

    try:
        if search_type == "playlist":
            results = sp.search(q=query, type="playlist", limit=1)
            items = results.get("playlists", {}).get("items", [])
            if items:
                sp.start_playback(context_uri=items[0]["uri"])
                return "Playing playlist: " + items[0]["name"]

        elif search_type == "artist":
            results = sp.search(q=query, type="artist", limit=1)
            items = results.get("artists", {}).get("items", [])
            if items:
                sp.start_playback(context_uri=items[0]["uri"])
                return "Playing " + items[0]["name"]

        elif search_type == "album":
            results = sp.search(q=query, type="album", limit=1)
            items = results.get("albums", {}).get("items", [])
            if items:
                sp.start_playback(context_uri=items[0]["uri"])
                return "Playing album: " + items[0]["name"]

        else:  # track
            results = sp.search(q=query, type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            if items:
                sp.start_playback(uris=[items[0]["uri"]])
                artist = items[0]["artists"][0]["name"]
                track = items[0]["name"]
                return "Playing " + track + " by " + artist

        return "I couldn't find anything matching '" + query + "', Sir."

    except spotipy.exceptions.SpotifyException as e:
        if "NO_ACTIVE_DEVICE" in str(e) or "Player command failed" in str(e):
            return "No active Spotify device found. Please open Spotify first, Sir."
        return "Spotify error: " + str(e)
    except Exception as e:
        return "Error: " + str(e)


def pause():
    """Pause playback."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        sp.pause_playback()
        return "Music paused."
    except:
        return "Nothing is playing, Sir."


def resume():
    """Resume playback."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        sp.start_playback()
        return "Resuming playback."
    except spotipy.exceptions.SpotifyException as e:
        if "NO_ACTIVE_DEVICE" in str(e):
            return "No active Spotify device. Please open Spotify first, Sir."
        return "Could not resume."


def next_track():
    """Skip to next track."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        sp.next_track()
        import time
        time.sleep(0.5)
        return now_playing()
    except:
        return "Could not skip track."


def previous_track():
    """Go to previous track."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        sp.previous_track()
        import time
        time.sleep(0.5)
        return now_playing()
    except:
        return "Could not go back."


def now_playing():
    """Get the currently playing track."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        current = sp.current_playback()
        if current and current.get("item"):
            track = current["item"]["name"]
            artist = current["item"]["artists"][0]["name"]
            album = current["item"]["album"]["name"]
            is_playing = current["is_playing"]
            state = "Playing" if is_playing else "Paused"
            return state + ": " + track + " by " + artist + " (" + album + ")"
        return "Nothing is currently playing, Sir."
    except:
        return "Could not check playback."


def set_spotify_volume(level):
    """Set Spotify volume (0-100)."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        sp.volume(int(level))
        return "Spotify volume set to " + str(level) + "%"
    except:
        return "Could not set volume."


def shuffle(state=True):
    """Toggle shuffle on/off."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        sp.shuffle(state)
        return "Shuffle " + ("on" if state else "off") + "."
    except:
        return "Could not toggle shuffle."


def repeat(state="track"):
    """Set repeat mode: track, context, or off."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        sp.repeat(state)
        return "Repeat set to " + state + "."
    except:
        return "Could not set repeat."


def play_liked_songs():
    """Play the user's liked/saved songs."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        results = sp.current_user_saved_tracks(limit=50)
        uris = [item["track"]["uri"] for item in results["items"]]
        if uris:
            sp.start_playback(uris=uris)
            return "Playing your liked songs, Sir."
        return "No liked songs found."
    except spotipy.exceptions.SpotifyException as e:
        if "NO_ACTIVE_DEVICE" in str(e):
            return "No active Spotify device. Please open Spotify first, Sir."
        return "Error: " + str(e)


def queue_track(query):
    """Add a track to the queue."""
    sp = get_spotify()
    if not sp:
        return "Spotify not configured."
    try:
        results = sp.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        if items:
            sp.add_to_queue(items[0]["uri"])
            artist = items[0]["artists"][0]["name"]
            track = items[0]["name"]
            return "Added to queue: " + track + " by " + artist
        return "Could not find that track."
    except:
        return "Could not add to queue."


# ── Intent Detection ──────────────────────────────────────────
def detect_media_command(message):
    """Detect music/media commands."""
    msg = message.lower().strip()

    # Now playing
    if any(w in msg for w in ["whats playing", "what's playing", "what song is this",
                               "current song", "currently playing", "what is playing",
                               "what am i listening to"]):
        return ("now_playing", None)

    # Pause
    if any(w in msg for w in ["pause music", "pause the music", "pause song",
                               "stop music", "stop the music", "pause spotify"]):
        return ("pause", None)

    # Resume
    if any(w in msg for w in ["resume music", "resume the music", "unpause",
                               "continue music", "resume spotify", "continue playing"]):
        return ("resume", None)

    # Next
    if any(w in msg for w in ["next song", "skip song", "skip this", "next track",
                               "skip track", "play next"]):
        return ("next", None)

    # Previous
    if any(w in msg for w in ["previous song", "go back", "last song", "previous track",
                               "play previous"]):
        return ("previous", None)

    # Shuffle
    if "shuffle on" in msg or "turn on shuffle" in msg or "enable shuffle" in msg:
        return ("shuffle", True)
    if "shuffle off" in msg or "turn off shuffle" in msg or "disable shuffle" in msg:
        return ("shuffle", False)

    # Repeat
    if "repeat song" in msg or "repeat this" in msg or "repeat track" in msg:
        return ("repeat", "track")
    if "repeat off" in msg or "stop repeating" in msg:
        return ("repeat", "off")

    # Liked songs
    if any(w in msg for w in ["play my liked", "play liked songs", "play my favorites",
                               "play my saved", "play favorites"]):
        return ("liked", None)

    # Queue
    if any(msg.startswith(w) for w in ["queue ", "add to queue "]):
        query = msg
        for trigger in ["add to queue ", "queue "]:
            if query.startswith(trigger):
                query = query[len(trigger):]
                break
        return ("queue", query)

    # Play specific content
    if any(msg.startswith(w) for w in ["play ", "put on ", "play some ", "play me "]):
        query = msg
        for trigger in ["play some ", "play me some ", "play me ", "put on some ",
                        "put on ", "play "]:
            if query.startswith(trigger):
                query = query[len(trigger):]
                break

        # Detect type
        if "playlist" in query:
            query = query.replace("playlist", "").strip()
            return ("play_playlist", query)
        elif "album" in query:
            query = query.replace("album", "").replace("the", "").strip()
            return ("play_album", query)
        elif any(w in msg for w in [" by ", " from "]):
            return ("play_track", query)
        else:
            # Could be genre, artist, or track — try track first
            return ("play_search", query)

    return (None, None)


def execute_media_command(action, args):
    """Execute a media command."""
    if action == "now_playing":
        return now_playing()
    elif action == "pause":
        return pause()
    elif action == "resume":
        return resume()
    elif action == "next":
        return next_track()
    elif action == "previous":
        return previous_track()
    elif action == "shuffle":
        return shuffle(args)
    elif action == "repeat":
        return repeat(args)
    elif action == "liked":
        return play_liked_songs()
    elif action == "queue":
        return queue_track(args)
    elif action == "play_playlist":
        return play_search(args, "playlist")
    elif action == "play_album":
        return play_search(args, "album")
    elif action == "play_track":
        return play_search(args, "track")
    elif action == "play_search":
        return play_search(args, "track")
    return "Unknown media command"
