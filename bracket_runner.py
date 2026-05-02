"""
Manages the state of an ongoing bracket tournament.
Tracks which clashes have been played, who won, and what's next.
"""


class BracketRunner:
    def __init__(self, bracket: dict, tracks: list[dict], settings: list[dict]):
        self.bracket  = bracket
        self.settings = {s["round"]: s for s in settings}
        self.size     = bracket["size"]
        self.rounds   = bracket["rounds"]
        self.losers   = set()  # set of slot indices (not URIs) that lost

        # slot_state[slot_idx] = track or None
        # Start by placing all assigned tracks into their starter slots
        total_slots = sum(self.size // (2 ** r) for r in range(self.rounds + 1))
        self.slot_state = [None] * total_slots

        for track in bracket["assigned"]:
            self.slot_state[track["starter_slot"]] = track

        self.round_offset = bracket["round_offset"]
        self.current_clash = None  # (slot_a, slot_b, result_slot)

    def find_next_clash(self):
        """
        Walks through slots in order, finds the next pair where:
        - Both slots are in the same match (adjacent even/odd pair)
        - At least one has a track
        - The result slot is empty
        Returns (track_a, track_b, result_slot) or None if bracket is complete.
        Auto-advances byes (one track, one empty).
        """
        for r in range(self.rounds):
            n_slots = self.size // (2 ** r)
            base    = self.round_offset[r]
            result_base = self.round_offset[r + 1]

            for m in range(0, n_slots, 2):
                slot_a = base + m
                slot_b = base + m + 1
                result_slot = result_base + m // 2

                track_a = self.slot_state[slot_a] if slot_a < len(self.slot_state) else None
                track_b = self.slot_state[slot_b] if slot_b < len(self.slot_state) else None
                result  = self.slot_state[result_slot] if result_slot < len(self.slot_state) else None

                # Skip if result already filled
                if result is not None:
                    continue

                # Skip if both empty
                if track_a is None and track_b is None:
                    continue

                # Auto-advance bye
                if track_a is not None and track_b is None:
                    self._advance(track_a, result_slot)
                    continue
                if track_b is not None and track_a is None:
                    self._advance(track_b, result_slot)
                    continue

                # Real clash
                self.current_clash = (slot_a, slot_b, result_slot, r)
                return track_a, track_b, result_slot, r

        return None  # Tournament complete

    def record_winner(self, winner_track: dict, loser_track: dict, result_slot: int):
        """Place the winner into the result slot and record the loser with votes."""
        if self.current_clash:
            slot_a, slot_b, _, _ = self.current_clash
            # Store votes on the original slot entries for display
            for slot in [slot_a, slot_b]:
                t = self.slot_state[slot]
                if t:
                    uri = t.get("uri", "")
                    if uri == loser_track.get("uri"):
                        t["votes"] = loser_track.get("votes", 0)
                        self.losers.add(slot)  # store slot, not URI
                    elif uri == winner_track.get("uri"):
                        t["votes"] = winner_track.get("votes", 0)
        self._advance(winner_track, result_slot)
        self.current_clash = None

    def _advance(self, track: dict, result_slot: int):
        t = dict(track)
        t["starter_slot"] = result_slot
        t.pop("votes", None)  # votes only belong to the slot where the clash happened
        self.slot_state[result_slot] = t

    def get_round_settings(self, round_index: int) -> dict:
        return self.settings.get(round_index, {"mode": 0, "seconds": None})

    def get_winner(self):
        """Returns the final winner if bracket is complete."""
        final_slot = self.round_offset[self.rounds]
        if final_slot < len(self.slot_state):
            return self.slot_state[final_slot]
        return None