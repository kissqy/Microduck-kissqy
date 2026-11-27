"""Metadata for the duckphone's preset actions.

The gestures themselves are played by `robotd` since protocol v42 — the daemon
owns the head and the mouth, and a phone with no Python host has to be able to
request the same motion the web page does. What stays here is what the *page*
and the idle director need to know about an action without asking the robot:
its label, the sound beat it belongs to, and whether the idle director may pick
it.

`robot.action` is the call; `robot.state`'s `act` / `actIdle` say what is
playing. Nothing in this file moves anything.
"""

from __future__ import annotations

ACTIONS = {
    "look_up": {
        "label": "抬头",
        "sound": "coo",
        "requires_walk": True,
    },
    "look_around": {
        "label": "左右看",
        "sound": "inquire",
        "requires_walk": True,
    },
    "circle": {
        "label": "画圈",
        "sound": "greet",
        "requires_walk": True,
    },
    "quack": {
        "label": "张嘴",
        "sound": "chirp",
        "requires_walk": True,
    },
}

IDLE_ACTION_NAMES = tuple(ACTIONS)


def action_sound(name: str) -> str | None:
    entry = ACTIONS.get(name)
    return entry["sound"] if entry else None
