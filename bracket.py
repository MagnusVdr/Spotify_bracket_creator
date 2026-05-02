import math
from bracketool.single_elimination import SingleEliminationGen
from bracketool.domain import Competitor


def build_bracket(tracks: list[dict]) -> dict:
    """
    Uses bracketool to generate a single-elimination bracket.
    Assigns each track a starter_slot and start_round.
    """
    se = SingleEliminationGen(
        use_three_way_final=False,
        third_place_clash=False,
        use_rating=False,
        use_teams=False
    )

    competitor_list = [Competitor(str(i), "", 0) for i in range(len(tracks))]
    output = se.generate(competitor_list)

    total_rounds      = len(output.rounds)
    first_round_size  = len(output.rounds[0]) * 2   # slots in round 0
    bracket_size      = first_round_size             # = next power of 2 >= n

    # Round offsets: R0=0, R1=bracket_size, R2=bracket_size+bracket_size//2, etc.
    round_offset = {}
    o = 0
    for r in range(total_rounds + 1):
        round_offset[r] = o
        o += bracket_size // (2 ** r)

    total_slots = o  # 2 * bracket_size - 1

    # Assign starter_slot to each track from round 0
    result_tracks = [dict(t) for t in tracks]
    slot_counter = round_offset[0]  # starts at 0

    for clash in output.rounds[0]:
        found = []
        for attr, val in vars(clash).items():
            if isinstance(val, (list, tuple)):
                for item in val:
                    if hasattr(item, 'name') and str(item.name).isdigit():
                        found.append(item)
                    elif hasattr(item, 'competitor') and item.competitor is not None:
                        found.append(item.competitor)
            else:
                if hasattr(val, 'name') and str(val.name).isdigit():
                    found.append(val)
                elif hasattr(val, 'competitor') and val.competitor is not None:
                    found.append(val.competitor)

        for i, comp in enumerate(found):
            track_idx = int(comp.name)
            result_tracks[track_idx]["starter_slot"] = slot_counter + i
            result_tracks[track_idx]["start_round"]  = 0
            result_tracks[track_idx]["M"]            = slot_counter + i

        slot_counter += 2

    # Tracks not assigned in round 0 are bye-advanced — find their round and slot
    # by checking subsequent rounds
    for r_idx in range(1, total_rounds):
        r_slot_counter = round_offset[r_idx]
        for clash in output.rounds[r_idx]:
            found = []
            for attr, val in vars(clash).items():
                if isinstance(val, (list, tuple)):
                    for item in val:
                        if hasattr(item, 'name') and str(item.name).isdigit():
                            found.append(item)
                        elif hasattr(item, 'competitor') and item.competitor is not None:
                            found.append(item.competitor)
                else:
                    if hasattr(val, 'name') and str(val.name).isdigit():
                        found.append(val)
                    elif hasattr(val, 'competitor') and val.competitor is not None:
                        found.append(val.competitor)

            for i, comp in enumerate(found):
                track_idx = int(comp.name)
                if "starter_slot" not in result_tracks[track_idx]:
                    result_tracks[track_idx]["starter_slot"] = r_slot_counter + i
                    result_tracks[track_idx]["start_round"]  = r_idx
                    result_tracks[track_idx]["M"]            = r_slot_counter + i

            r_slot_counter += 2

    return {
        "size":         bracket_size,
        "rounds":       total_rounds,
        "round_offset": round_offset,
        "total_slots":  total_slots,
        "slot_array":   result_tracks,  # indexed by track order, not slot
        "assigned":     result_tracks,
    }


def get_round_name(rounds_total: int, round_index: int) -> str:
    rounds_left = rounds_total - round_index
    if rounds_left == 0:
        return "Winner"
    if rounds_left == 1:
        return "Final"
    if rounds_left == 2:
        return "Semi-Final"
    if rounds_left == 3:
        return "Quarter-Final"
    return f"Round of {2 ** rounds_left}"


if __name__ == "__main__":
    tracks = [{"name": f"T{i}", "artists": ""} for i in range(47)]
    b = build_bracket(tracks)
    print(f"bracket_size={b['size']}, rounds={b['rounds']}, total_slots={b['total_slots']}")
    print(f"round_offset={b['round_offset']}\n")
    for t in b["assigned"]:
        print(f"  start_round={t['start_round']}  starter_slot={t['starter_slot']:3d}  {t['name']}")