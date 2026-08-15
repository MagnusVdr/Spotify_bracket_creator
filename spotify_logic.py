import os
import re
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
from io import BytesIO

CREDS_FILE = "credentials.txt"


def load_credentials(filepath=CREDS_FILE):
    """Reads credentials from the text file. Returns (client_id, client_secret)."""
    creds = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    creds[key.strip()] = value.strip()
        return creds.get("CLIENT_ID"), creds.get("CLIENT_SECRET")
    except FileNotFoundError:
        return None, None


def save_credentials(client_id: str, client_secret: str, filepath=CREDS_FILE) -> None:
    """Writes credentials back to the text file so they're pre-filled next launch."""
    with open(filepath, "w") as f:
        f.write(f"CLIENT_ID={client_id}\n")
        f.write(f"CLIENT_SECRET={client_secret}\n")


REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-private playlist-read-collaborative user-library-read user-read-playback-state user-modify-playback-state"


class SpotifyClient:
    def __init__(self, client_id: str = None, client_secret: str = None, creds_file=CREDS_FILE):
        # Fall back to the file only if nothing was passed in
        if not client_id or not client_secret:
            client_id, client_secret = load_credentials(creds_file)

        if not client_id or not client_secret or "your_id" in client_id:
            raise ValueError("Please enter a valid Spotify Client ID and Client Secret.")

        self.client_id = client_id

        # Cache path is tied to the client id, so switching credentials
        # doesn't reuse a token issued to a different app.
        cache_path = f".cache-{client_id[:12]}"

        self._sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=cache_path
        ))

    def verify(self) -> None:
        """
        Forces the OAuth flow / token refresh now instead of on the first
        playlist call, so bad credentials fail immediately with a clear error.
        """
        self._sp.current_user()

    def get_image_data(self, url: str):
        """
        Downloads the raw image bytes from a URL.
        This is what you pass to your GUI's image label.
        """
        if not url:
            return None
        response = requests.get(url)
        return response.content

    def _extract_playlist_id(self, playlist_link: str) -> str:
        # 1. Handle full URLs (https://open.spotify.com/playlist/...)
        if "playlist/" in playlist_link:
            match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_link)
            if match:
                return match.group(1)

        # 2. Handle bare IDs that might have tracking attached (the ?si= part)
        clean_id = playlist_link.split('?')[0].strip()

        if len(clean_id) == 22:
            return clean_id

        raise ValueError(f"Could not extract a valid ID from: {playlist_link}")

    def get_playlist_tracks(self, playlist_link: str) -> list[dict]:
        playlist_id = self._extract_playlist_id(playlist_link)
        tracks = []

        results = self._sp.playlist_items(playlist_id, additional_types=['track', 'episode'])

        while results:
            for entry in results.get('items', []):
                t = entry.get('track') or entry.get('item')

                if not t:
                    continue

                item_type = t.get('type')

                # --- Handle Standard Music Tracks ---
                if item_type == 'track':
                    album = t.get('album', {})
                    album_name = album.get('name', "Unknown Album")
                    images = album.get('images', [])

                    artists = t.get('artists', [])
                    artist_names = ", ".join([a.get('name') for a in artists]) if artists else "Unknown Artist"

                # --- Handle Podcast Episodes ---
                elif item_type == 'episode':
                    show = t.get('show', {})
                    album_name = show.get('name', "Unknown Show")
                    images = t.get('images', []) or show.get('images', [])
                    artist_names = show.get('publisher', "Unknown Publisher")

                else:
                    continue

                image_url = images[0].get('url') if images else None

                track_obj = {
                    "uri": t.get("uri"),
                    "name": t.get("name", "Unknown Track"),
                    "album_name": album_name,
                    "artists": artist_names,
                    "duration_ms": t.get("duration_ms", 0),
                    "image_url": image_url,
                    "type": item_type
                }
                tracks.append(track_obj)

            if results.get('next'):
                results = self._sp.next(results)
            else:
                break

        return tracks

    def play_track(self, uri: str, start_ms: int = 0):
        """Plays a track from a specific millisecond."""
        try:
            self._sp.start_playback(uris=[uri], position_ms=start_ms)
        except Exception as e:
            print(f"Playback Error: {e}")

    def stop_playback(self):
        self._sp.pause_playback()


if __name__ == "__main__":
    PLAYLIST = "https://open.spotify.com/playlist/3WlBaNZQAPEp6WxGn96rQC?si=4be92312ca234316"

    client = SpotifyClient()
    try:
        tracks = client.get_playlist_tracks(PLAYLIST)
        print(f"--- Found {len(tracks)} tracks ---\n")
        for i, track in enumerate(tracks[:10], 1):
            print(f"{i}. {track['name']} - {track['artists']}")
    except Exception as e:
        print(f"Error: {e}")