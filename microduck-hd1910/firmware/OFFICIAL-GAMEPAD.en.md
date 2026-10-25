[简体中文](OFFICIAL-GAMEPAD.zh-CN.md) | **English** | [Русский](OFFICIAL-GAMEPAD.ru.md)

# R17 v1.0.97 / official 0.15.1 gamepad

The R7 GameSir Xbox bridge binary and mapping carry over from R17. Official padd is compiled unchanged. The webpage generates standard Xbox evdev input, rather than custom robot.move or automatic hold / start / stop sequences.

- Start: first HOME; afterwards toggle the official policy, returning to HOME when disabled.
- Select: short press then release unloads torque; holding for 2 seconds runs the official sit / shutdown sequence.
- Left / right sticks: speed, turning, head, or body pose according to official mode and `[pad]` parameters.
- Y: head mode. B: body mode. LT / RT: official calls and beak actions.
- D-pad down: original 10000-iteration sit / stand.
- Skill buttons without models are disabled in the page; A, X, LB, and RB are unbound in `[pad]`.

When a physical controller appears, the backend destroys the web evdev device and discards pending frames. A 600 ms web-input timeout also destroys it. The first web press waits for read-only `pad.input` attachment confirmation so the official 500 ms discovery interval cannot miss Start.

Takeover does not synthesize a Select release or issue separate robot.stop / robot.enable commands. Official padd still handles disconnect / release behavior. Full key / axis definitions are in `packaging/webpad.py` and the original `gamepad-r7/gamesir-xboxd.c`.
