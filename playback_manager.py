import os
import random
import pygame

from youtube_client import download_audio

pygame.mixer.init()

DEFAULT_VOLUME = 0.5


class PlaybackManager:
    def __init__(self, spotify_client):
        self._spotify       = spotify_client
        self._current_source = "spotify"
        self._current_tmp   = None  # path to temp mp3 for cleanup
        self._volume        = DEFAULT_VOLUME
        pygame.mixer.music.set_volume(self._volume)

    def set_volume(self, volume: float):
        """0.0 to 1.0"""
        self._volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self._volume)

    def play(self, track: dict, start_ms: int = 0):
        self.stop()
        source = track.get("source", "spotify")
        self._current_source = source
        if source == "youtube":
            self._play_youtube(track, start_ms)
        else:
            self._play_spotify(track, start_ms)

    def play_random_start(self, track: dict, duration_ms: int):
        track_duration = track.get("duration_ms", 0)
        if track_duration > duration_ms:
            start_ms = random.randint(0, track_duration - duration_ms)
        else:
            start_ms = 0
        self.play(track, start_ms)

    def stop(self):
        if self._current_source == "youtube":
            self._stop_youtube()
        else:
            self._stop_spotify()

    # ── Spotify ──────────────────────────────────────────────────────────────

    def _play_spotify(self, track: dict, start_ms: int):
        try:
            self._spotify.play_track(track["uri"], start_ms=start_ms)
        except Exception as e:
            print(f"[Spotify] Playback error: {e}")

    def _stop_spotify(self):
        try:
            self._spotify.stop_playback()
        except Exception:
            pass  # 403 restriction errors are harmless — player already stopped

    # ── YouTube (pygame) ─────────────────────────────────────────────────────

    def _play_youtube(self, track: dict, start_ms: int):
        try:
            print(f"[YouTube] Downloading: {track['name']}")
            mp3_path = download_audio(track["uri"])
            self._current_tmp = mp3_path
            pygame.mixer.music.load(mp3_path)
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.play(start=start_ms / 1000)
            print(f"[YouTube] Playing from {start_ms // 1000}s")
        except Exception as e:
            print(f"[YouTube] Playback error: {e}")

    def _stop_youtube(self):
        pygame.mixer.music.stop()
        self._cleanup_tmp()

    def _cleanup_tmp(self):
        if self._current_tmp and os.path.exists(self._current_tmp):
            try:
                pygame.mixer.music.unload()
                os.remove(self._current_tmp)
                tmp_dir = os.path.dirname(self._current_tmp)
                if os.path.isdir(tmp_dir):
                    os.rmdir(tmp_dir)
            except Exception as e:
                print(f"[YouTube] Cleanup error: {e}")
            self._current_tmp = None