"""
Saves and loads the full bracket state to/from a JSON file.
Called after every lock-in so crashes don't lose progress.
"""
import json
import os

SAVE_FILE = "bracket_state.json"


def save_state(tracks: list[dict], bracket: dict, runner) -> None:
    state = {
        "tracks": _serialize_tracks(tracks),
        "bracket": _serialize_bracket(bracket),
        "runner": _serialize_runner(runner),
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_state() -> dict | None:
    if not os.path.exists(SAVE_FILE):
        return None
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[StateManager] Failed to load save: {e}")
        return None


def delete_state() -> None:
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)


def has_save() -> bool:
    return os.path.exists(SAVE_FILE)


# ── Serializers ───────────────────────────────────────────────────────────────

def _serialize_tracks(tracks: list[dict]) -> list[dict]:
    safe_keys = {"name", "artists", "uri", "duration_ms", "image_url",
                 "source", "stream_url", "start_times_ms",
                 "starter_slot", "start_round", "M", "seed_slot"}
    result = []
    for t in tracks:
        result.append({k: v for k, v in t.items() if k in safe_keys})
    return result


def _serialize_bracket(bracket: dict) -> dict:
    return {
        "size":         bracket.get("size"),
        "rounds":       bracket.get("rounds"),
        "round_offset": bracket.get("round_offset"),
        "assigned":     _serialize_tracks(bracket.get("assigned", [])),
        "losers":       list(bracket.get("losers", set())),
    }


def _serialize_runner(runner) -> dict:
    slot_state = []
    for t in runner.slot_state:
        if t is None:
            slot_state.append(None)
        else:
            slot_state.append({k: v for k, v in t.items()
                                if not callable(v) and isinstance(v, (str, int, float, bool, list, type(None)))})
    return {
        "slot_state": slot_state,
        "losers":     list(runner.losers),
        "settings":   {str(k): v for k, v in runner.settings.items()},
    }


# ── Deserializers ─────────────────────────────────────────────────────────────

def restore_bracket(bracket_data: dict) -> dict:
    bracket_data["losers"] = set(bracket_data.get("losers", []))
    # Restore round_offset keys as ints
    bracket_data["round_offset"] = {int(k): v for k, v in bracket_data["round_offset"].items()}
    # Rebuild slot_array from assigned
    size = bracket_data["size"]
    slot_array = [None] * size
    for t in bracket_data["assigned"]:
        seed = t.get("seed_slot")
        if seed is not None and seed < size:
            slot_array[seed] = t
    bracket_data["slot_array"] = slot_array
    return bracket_data


def restore_runner(runner, runner_data: dict) -> None:
    runner.slot_state = runner_data["slot_state"]
    runner.losers     = set(runner_data["losers"])
    runner.settings   = {int(k): v for k, v in runner_data["settings"].items()}
