import re
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
from io import BytesIO

def load_credentials(filepath="credentials.txt"):
    """Reads credentials from the text file."""
    creds = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    creds[key] = value
        return creds.get("CLIENT_ID"), creds.get("CLIENT_SECRET")
    except FileNotFoundError:
        return None, None

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-private playlist-read-collaborative user-library-read user-read-playback-state user-modify-playback-state"


class SpotifyClient:
    def __init__(self, creds_file="credentials.txt"):
        client_id, client_secret = load_credentials(creds_file)

        if not client_id or not client_secret or "your_id" in client_id:
            raise ValueError(f"Please update {creds_file} with valid Spotify API keys.")

        # 2. Initialize Spotipy
        self._sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE
        ))

    def get_image_data(self, url: str):
        """
        Downloads the raw image bytes from a URL.
        This is what you pass to your GUI's image label.
        """
        if not url:
            return None
        response = requests.get(url)
        # Returns raw bytes that libraries like PIL or Tkinter can use
        return response.content

    def _extract_playlist_id(self, playlist_link: str) -> str:
        # 1. Handle full URLs (https://open.spotify.com/playlist/...)
        if "playlist/" in playlist_link:
            # Match alphanumeric characters after 'playlist/' until it hits a '?' or '/'
            match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_link)
            if match:
                return match.group(1)
                
        # 2. Handle bare IDs that might have tracking attached (the ?si= part)
        # We take the string and split it at '?', then take the first part
        clean_id = playlist_link.split('?')[0].strip()
        
        # Standard Spotify IDs are usually 22 characters long
        if len(clean_id) == 22:
            return clean_id
            
        raise ValueError(f"Could not extract a valid ID from: {playlist_link}")

    def get_playlist_tracks(self, playlist_link: str) -> list[dict]:
        playlist_id = self._extract_playlist_id(playlist_link)
        tracks = []
        
        # 1. CRITICAL: Add additional_types to fetch episodes too
        results = self._sp.playlist_items(playlist_id, additional_types=['track', 'episode'])
        
        while results:
            for entry in results.get('items', []):
                t = entry.get('track') or entry.get('item')
                
                # Spotify sometimes returns None for local files or unavailable tracks
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
                    # Use the podcast show name as the "album"
                    album_name = show.get('name', "Unknown Show")
                    # Episodes usually have images at the root level, or inside 'show'
                    images = t.get('images', []) or show.get('images', [])
                    
                    # Use the podcast publisher as the "artist"
                    artist_names = show.get('publisher', "Unknown Publisher")
                
                else:
                    # Skip anything that isn't a track or episode
                    continue

                # Get the highest resolution image if available
                image_url = images[0].get('url') if images else None
                
                # Construct the custom Data Structure
                track_obj = {
                    "uri": t.get("uri"),
                    "name": t.get("name", "Unknown Track"),
                    "album_name": album_name,
                    "artists": artist_names, 
                    "duration_ms": t.get("duration_ms", 0),
                    "image_url": image_url,
                    "type": item_type # Handy to keep track of what it is!
                }
                tracks.append(track_obj)
            
            # Pagination
            if results.get('next'):
                results = self._sp.next(results)
            else:
                break

        return tracks

    def play_track(self, uri: str, start_ms: int = 0):
        """
        Plays a track from a specific millisecond.
        """
        try:
            self._sp.start_playback(uris=[uri], position_ms=start_ms)
        except Exception as e:
            # Common error: No active device found
            print(f"Playback Error: {e}")

    def stop_playback(self):
        self._sp.pause_playback()


if __name__ == "__main__":
    # Use a guaranteed live link
    PLAYLIST = "https://open.spotify.com/playlist/3WlBaNZQAPEp6WxGn96rQC?si=4be92312ca234316" 
    # Add this to your __main__ block

    client = SpotifyClient()
    try:
        tracks = client.get_playlist_tracks(PLAYLIST)
        print(f"--- Found {len(tracks)} tracks ---\n")
        for i, track in enumerate(tracks[:10], 1): 
            print(f"{i}. {track['name']} - {track['artist']}")
    except Exception as e:
        print(f"Error: {e}")
