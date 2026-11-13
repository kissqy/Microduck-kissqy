#!/bin/sh
# How reliable is the radio between the pad and the robot?
#
# Run this on the robot, with the pad switched on and `padd` doing whatever it normally does. It
# reads the same evdev node gilrs reads, and reading an input device does not take it away from
# anyone — so this measures the link while the robot is being driven, which is the only condition
# worth measuring it in.
#
# WHAT IT MEASURES, AND WHY TWO THINGS. A pad link fails in two ways that look nothing alike:
#
#   - it *drops*. The device disappears, `padd` logs "pad gone", robotd's deadman stops the robot.
#     Loud, already in the journal, and counted here from the same evidence gilrs uses: whether the
#     event node exists.
#   - it *stalls*. The connection stays up and the reports stop arriving for a few hundred
#     milliseconds. Nothing anywhere records this today: `padd` polls the last known stick value and
#     keeps sending it at 50 Hz, so robotd sees fresh intents, the deadman never fires, and the robot
#     walks on a stale command. This is the reason the script reads the raw event stream rather than
#     just watching for disconnects.
#
# MOVE THE STICKS. An evdev device sends nothing when nothing changes, so a pad resting on a table
# is indistinguishable from a link that has stopped delivering. Gaps are only evidence while someone
# is driving. A silence longer than `IDLE_MS` is separated out rather than counted as a stall — that
# much silence with the link still up can only be a pad at rest — but it is still measurement time
# spent on nothing, so the report says how much of the window was actually driven and refuses to
# reach a verdict when that is too little.
#
# Usage:  scripts/pad-link-test.sh [--seconds N] [--mac AA:BB:..]
#         scripts/pad-link-test.sh --history [--since -7d]
#
# Exit: 0 the measurement ran; 1 it could not run.
set -eu

DURATION=120
MAC=
MODE=watch
SINCE=-7d

# The three thresholds below have a compiled twin in `duck_ipc_proto::pad_link`, which
# `robotctl monitor`'s live pad block reads them from. Deliberately two copies: this file has to run
# on a board with none of that compiled, and it is `scp`-ed there on its own. They must agree — two
# tools that disagree about what counts as a stall are two tools nobody can compare — so change both.
#
# Where the deadman zeroes the velocity, from robotd's default `safety.deadman_ms`. A stall longer
# than this is not a latency complaint, it is the robot stopping.
DEADMAN_MS=500

# Under this a stall is invisible to a driver; over it, it is the robot feeling sticky. Reported
# separately from the deadman because they are different complaints with the same cause.
NOTABLE_MS=100

# Past this, silence is the operator rather than the radio. It is not a guess: a link that stopped
# delivering for this long would have hit its supervision timeout and dropped, and a drop is counted
# separately and loudly. So a five-second hole with the link still up means the sticks were at rest.
#
# Counting those as stalls made the first real run report three breaches of the deadman on a link
# that never faltered — the longest of them 75 seconds, which is a pad on a table, not a radio.
IDLE_MS=5000

while [ $# -gt 0 ]; do
    case "$1" in
        --seconds) shift; DURATION="${1:?--seconds needs a value}" ;;
        --mac) shift; MAC="${1:?--mac needs a value}" ;;
        --history) MODE=history ;;
        --since) shift; SINCE="${1:?--since needs a value}" ;;
        -h|--help)
            cat <<'USAGE'
usage: pad-link-test.sh [--seconds N] [--mac AA:BB:CC:DD:EE:FF]
       pad-link-test.sh --history [--since -7d]

Measure the Bluetooth link between a gamepad and this robot: how often it drops, and how late the
input reports arrive while it is up. Run it on the robot; padd can keep running.

  --seconds N   how long to watch (default 120)
  --mac ADDR    which pad, when more than one is connected
  --history     do not measure anything: count the drops already in padd's journal
  --since WHEN  how far back --history looks (default -7d, any journalctl --since value)

Move the sticks continuously while it watches. A still pad sends nothing, and silence cannot be
told apart from a stalled link.
USAGE
            exit 0
            ;;
        *) echo "pad-link-test.sh: unknown argument: $1" >&2; exit 1 ;;
    esac
    shift
done

die() {
    echo "pad-link-test.sh: $*" >&2
    exit 1
}

# Checked rather than left to the arithmetic below, which under `set -eu` would exit on a syntax
# error from expanding it and say nothing about which argument was wrong.
case "$DURATION" in
    ''|*[!0-9]*) die "--seconds wants a whole number of seconds, not: ${DURATION}" ;;
esac
[ "$DURATION" -gt 0 ] || die "--seconds wants at least one second"

# Bluetooth, in /proc/bus/input/devices terms. A pad on USB is 0003, and that is worth telling
# someone apart from "no pad at all": there is no radio to test.
BUS_BLUETOOTH=0005
BUS_USB=0003

# Overridable so the parse below can be exercised against a captured file on a machine that has no
# pad, and no /proc worth the name.
INPUT_DEVICES="${PAD_INPUT_DEVICES:-/proc/bus/input/devices}"

# Every pad on a given bus, one per line: event node, name, address.
#
# This is the same evidence `padd` acts on — gilrs finds pads through udev and evdev, so a pad this
# cannot see is a pad that cannot drive, whatever `bluetoothctl` believes about it.
#
# A pad is a device with a *joystick* handler, not merely an event node. One Xbox controller
# registers several input devices — the pad, and a consumer-control keyboard for its media keys,
# which arrive interleaved and in no useful order. Taking the first event node measured the media
# keys, which never send anything, and reported a link that had gone perfectly silent.
pads_on_bus() {
    # $1 bus, $2 address to insist on or empty for any, $3 non-empty to refuse the fallback below
    awk -v bus="$1" -v want="$2" -v strict="$3" '
        BEGIN { RS = ""; FS = "\n" }
        {
            b = ""; name = ""; uniq = ""; ev = ""; js = 0
            for (i = 1; i <= NF; i++) {
                if ($i ~ /^I:/ && match($i, /Bus=[0-9a-fA-F]+/))
                    b = substr($i, RSTART + 4, RLENGTH - 4)
                else if ($i ~ /^N: Name=/) {
                    name = $i; sub(/^N: Name="/, "", name); sub(/"$/, "", name)
                } else if ($i ~ /^U: Uniq=/) {
                    uniq = $i; sub(/^U: Uniq=/, "", uniq)
                } else if ($i ~ /^H: Handlers=/) {
                    if (match($i, /event[0-9]+/)) ev = substr($i, RSTART, RLENGTH)
                    if ($i ~ /js[0-9]/) js = 1
                }
            }
            if (b != bus || ev == "") next
            if (want != "" && tolower(uniq) != tolower(want)) next
            line = ev "\t" name "\t" uniq
            if (js) pads[++n] = line; else others[++m] = line
        }
        # The fallback is for a board with no joydev module, where nothing has a js node and the
        # choice is between guessing and refusing to run. Probing a bus for "is there a pad on it"
        # cannot afford it — every keyboard would answer yes.
        END {
            for (i = 1; i <= n; i++) print pads[i]
            if (n == 0 && strict == "")
                for (i = 1; i <= m; i++) print others[i]
        }
    ' "$INPUT_DEVICES"
}

# Seconds since boot, in hundredths. Monotonic on purpose: a test that runs for two minutes must not
# be confused by NTP stepping the wall clock underneath it.
now_cs() {
    cut -d' ' -f1 < /proc/uptime | tr -d '.'
}

secs() {
    # $1 centiseconds -> "12.3 s"
    awk -v cs="$1" 'BEGIN { printf "%.1f s", cs / 100 }'
}

# ---------------------------------------------------------------------------- history

if [ "$MODE" = history ]; then
    command -v journalctl >/dev/null 2>&1 || die "no journalctl, so there is no history to read"

    # `padd` logs both edges of a pad's presence at warn, once per transition, so its journal is
    # already a drop log for every robot that has ever been driven. Nothing had to be running for
    # this to be true, which is why it is worth asking before spending two minutes measuring.
    lines="$(journalctl -u padd --since "$SINCE" --no-pager -o short-iso 2>/dev/null \
        | grep -E 'pad connected|pad gone' || true)"

    if [ -z "$lines" ]; then
        echo "no pad ever connected or dropped in padd's journal since ${SINCE}."
        echo "Either nobody has driven this robot in that window, or padd is not running:"
        echo "  robotctl pad status"
        exit 0
    fi

    drops="$(printf '%s\n' "$lines" | grep -c 'pad gone' || true)"
    ups="$(printf '%s\n' "$lines" | grep -c 'pad connected' || true)"
    echo "padd journal since ${SINCE}"
    echo "  connects   ${ups}"
    echo "  drops      ${drops}"
    echo
    printf '%s\n' "$lines" | tail -40
    echo

    # The reason, which padd cannot know. 0x08 is a supervision timeout — out of range, or something
    # else on 2.4 GHz. 0x13 and 0x16 are somebody switching the pad off, and are not a fault.
    kernel="$(journalctl -k --since "$SINCE" --no-pager 2>/dev/null \
        | grep -iE 'hci|bluetooth' | grep -iE 'disconn|timeout|link' || true)"
    if [ -n "$kernel" ]; then
        echo "kernel, same window (0x08 = supervision timeout: range or interference)"
        printf '%s\n' "$kernel" | tail -20
    fi
    exit 0
fi

# ---------------------------------------------------------------------------- preflight

[ -r "$INPUT_DEVICES" ] || die "cannot read ${INPUT_DEVICES}"

pad="$(pads_on_bus "$BUS_BLUETOOTH" "$MAC" "" | head -1)"
if [ -z "$pad" ]; then
    usb="$(pads_on_bus "$BUS_USB" "" strict | head -1)"
    if [ -n "$usb" ]; then
        die "no pad on Bluetooth. There is one on USB ($(printf '%s' "$usb" | cut -f2)),
  and a cable has no reliability to measure. Unplug it and switch the pad on."
    fi
    die "no pad connected over Bluetooth. Switch it on and wait a moment, then:
  robotctl pad status"
fi

node="/dev/input/$(printf '%s' "$pad" | cut -f1)"
name="$(printf '%s' "$pad" | cut -f2)"
addr="$(printf '%s' "$pad" | cut -f3)"

[ -r "$node" ] || die "cannot read ${node} — input devices are root-only on this board:
  sudo sh $0"

count="$(pads_on_bus "$BUS_BLUETOOTH" "$MAC" "" | wc -l | tr -d ' ')"
if [ "$count" -gt 1 ]; then
    echo "note: ${count} Bluetooth pads connected; measuring ${name}. --mac picks another."
fi

# The event stream is decoded by width, so the struct has to be the one this assumes: 8-byte
# seconds, 8-byte microseconds, then type/code/value. That is a 64-bit kernel. On anything else the
# drop counting below is still right and the cadence numbers would be nonsense, so they are skipped.
CADENCE=1
if [ "$(getconf LONG_BIT 2>/dev/null || echo 64)" != 64 ]; then
    CADENCE=
    echo "note: 32-bit userland — counting drops only, not report cadence."
fi
command -v timeout >/dev/null 2>&1 || die "no timeout(1); this needs coreutils"
if ! od -A n -t u8 -w24 -v < /dev/null >/dev/null 2>&1; then
    CADENCE=
    echo "note: od(1) here has no -w — counting drops only, not report cadence."
fi

# od buffers by block, and the run ends by killing it, so without this the last few seconds of
# events die in the buffer. Not fatal if stdbuf is missing; the tail is simply lost.
STDBUF=
if command -v stdbuf >/dev/null 2>&1; then
    STDBUF=1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
raw="$tmp/events"
timeline="$tmp/timeline"
: > "$raw"
: > "$timeline"

driver="$(systemctl is-active padd 2>/dev/null || true)"

echo "pad     ${name} ${addr}  ${node}"
echo "padd    ${driver:-unknown}"
echo
echo "watching for ${DURATION}s. Move the sticks continuously — a pad at rest sends nothing, and"
echo "silence cannot be told apart from a stalled link. Walking away from the robot is how you find"
echo "the range."
echo

# ---------------------------------------------------------------------------- watch

sample() {
    # $1 seconds to read for. Returns when the device disappears or the time is up; both are
    # ordinary outcomes, and a vanished device is the measurement rather than an error.
    if [ -n "$STDBUF" ]; then
        timeout "$1" stdbuf -oL od -A n -t u8 -w24 -v < "$node" >> "$raw" 2>/dev/null || true
    else
        timeout "$1" od -A n -t u8 -w24 -v < "$node" >> "$raw" 2>/dev/null || true
    fi
}

start_cs="$(now_cs)"
end_cs=$((start_cs + DURATION * 100))
connected=1
drops=0
up_cs=0
since_cs="$start_cs"

while :; do
    cs="$(now_cs)"
    [ "$cs" -lt "$end_cs" ] || break

    # Re-resolved every pass rather than held: a pad that comes back can come back as a different
    # event number, and a script that kept the old path would report the rest of the window as one
    # long outage.
    found="$(pads_on_bus "$BUS_BLUETOOTH" "${MAC:-$addr}" "" | head -1)"

    if [ -n "$found" ]; then
        node="/dev/input/$(printf '%s' "$found" | cut -f1)"
        if [ "$connected" -eq 0 ]; then
            connected=1
            printf '  +%s  back after %s\n' "$(secs $((cs - start_cs)))" "$(secs $((cs - since_cs)))" \
                | tee -a "$timeline"
            since_cs="$cs"
        fi
        if [ -n "$CADENCE" ]; then
            # A marker, so a gap that spans a reconnection is not counted as one enormous stall.
            echo break >> "$raw"
            rem=$(((end_cs - cs + 99) / 100))
            if [ "$rem" -lt 1 ]; then rem=1; fi
            sample "$rem"
            # A device being removed reaches /proc and /dev at different moments, so `sample` can
            # return instantly on a node that is already gone while the pad is still listed. Without
            # this the loop spins at full CPU for the rest of the window — on a robot that is being
            # driven, and by the tool brought in to find out why driving is unreliable.
            if [ "$(now_cs)" -eq "$cs" ]; then
                sleep 0.2
            fi
        else
            sleep 1
        fi
    else
        if [ "$connected" -eq 1 ]; then
            connected=0
            drops=$((drops + 1))
            up_cs=$((up_cs + cs - since_cs))
            printf '  +%s  gone\n' "$(secs $((cs - start_cs)))" | tee -a "$timeline"
            since_cs="$cs"
        fi
        sleep 0.2
    fi
done

cs="$(now_cs)"
if [ "$connected" -eq 1 ]; then
    up_cs=$((up_cs + cs - since_cs))
fi
window_cs=$((cs - start_cs))

# ---------------------------------------------------------------------------- report

# One report ends with a SYN_REPORT — type 0, code 0, value 0, which is the whole third column being
# zero once od has packed those three fields into one 8-byte word. Counting every event instead
# would count each axis of a stick separately and turn one late report into four.
#
# SYN_DROPPED (type 0, code 3) means *this reader* fell behind and the kernel discarded events for
# it. It says nothing about the radio, and it invalidates the gap either side of it, so it is
# reported rather than silently folded in.
stats="0 0 0 0 0 0 0 0"
if [ -n "$CADENCE" ] && [ -s "$raw" ]; then
    stats="$(awk -v notable="$NOTABLE_MS" -v deadman="$DEADMAN_MS" -v idle="$IDLE_MS" '
        NF != 3 { prev = 0; next }
        $3 == 196608 { dropped++; prev = 0; next }
        $3 != 0 { next }
        {
            t = $1 * 1000 + int($2 / 1000)
            n++
            if (prev > 0) {
                d = t - prev
                if (d > idle) {
                    quiet++
                    if (d > longest_quiet) longest_quiet = d
                } else {
                    driving += d
                    if (d > worst) worst = d
                    if (d > notable) over_notable++
                    if (d > deadman) over_deadman++
                }
            }
            prev = t
        }
        END {
            printf "%d %d %d %d %d %d %d %d\n",
                n, worst, over_notable, over_deadman, dropped, quiet, longest_quiet, driving
        }
    ' "$raw")"
fi

reports="$(echo "$stats" | cut -d' ' -f1)"
worst="$(echo "$stats" | cut -d' ' -f2)"
over_notable="$(echo "$stats" | cut -d' ' -f3)"
over_deadman="$(echo "$stats" | cut -d' ' -f4)"
syn_dropped="$(echo "$stats" | cut -d' ' -f5)"
quiet="$(echo "$stats" | cut -d' ' -f6)"
longest_quiet="$(echo "$stats" | cut -d' ' -f7)"
driving_ms="$(echo "$stats" | cut -d' ' -f8)"

# Every arithmetic expression handed to printf is parenthesised, and has to be. `printf "%.1f", b > 0
# ? x : y` reads the `>` as a redirection: awk writes the number to a *file* called 0 in the working
# directory and prints an empty field, which is exactly what the first run on a board did.
ratio() {
    # $1 numerator, $2 denominator, $3 scale — empty when there is nothing to divide by
    awk -v a="$1" -v b="$2" -v s="$3" 'BEGIN { printf "%.1f", (b > 0 ? s * a / b : 0) }'
}

echo
echo "link"
printf '  window       %s\n' "$(secs "$window_cs")"
printf '  connected    %s  (%s%%)\n' "$(secs "$up_cs")" "$(ratio "$up_cs" "$window_cs" 100)"
printf '  drops        %s\n' "$drops"
if [ -s "$timeline" ]; then
    cat "$timeline"
fi

if [ -n "$CADENCE" ]; then
    echo
    echo "input"
    # Rated against the time the sticks were actually moving, not the window. Against the window it
    # reads as a catastrophically slow pad whenever someone pauses, which is every real session.
    printf '  driving      %s of %s\n' "$(secs $((driving_ms / 10)))" "$(secs "$window_cs")"
    printf '  reports      %s  (%s/s while driving)\n' "$reports" \
        "$(ratio "$reports" "$driving_ms" 1000)"
    printf '  worst gap    %s ms\n' "$worst"
    printf '  over %s ms  %s\n' "$NOTABLE_MS" "$over_notable"
    printf '  over %s ms  %s   (robotd zeroes the velocity here)\n' "$DEADMAN_MS" "$over_deadman"
    if [ "$quiet" -gt 0 ]; then
        printf '  quiet        %s spells, longest %s   (the sticks at rest, not the link:\n' \
            "$quiet" "$(secs $((longest_quiet / 10)))"
        printf '               a link silent that long would have dropped, and none did)\n'
    fi
    if [ "$syn_dropped" -gt 0 ]; then
        printf '  syn_dropped  %s   (this reader fell behind; gaps around it mean nothing)\n' \
            "$syn_dropped"
    fi
fi

# A verdict is only worth as much as the driving behind it. Ten seconds is not a standard, it is the
# point below which saying "the link held" would be a claim about nothing.
THIN_MS=10000

echo
if [ -n "$CADENCE" ] && [ "$reports" -eq 0 ]; then
    echo "verdict  nothing arrived at all. If the sticks were moving, this is not a link that works;"
    echo "         if they were not, run it again and keep them moving."
elif [ -n "$CADENCE" ] && [ "$driving_ms" -lt "$THIN_MS" ] && [ "$drops" -eq 0 ]; then
    printf 'verdict  too little driving to judge: %s of stick movement in a %s window, and no drops.\n' \
        "$(secs $((driving_ms / 10)))" "$(secs "$window_cs")"
    echo "         Run it again and keep the sticks moving the whole time."
elif [ "$drops" -eq 0 ] && [ "$over_deadman" -eq 0 ] && [ "$over_notable" -eq 0 ]; then
    echo "verdict  the link held, with nothing over ${NOTABLE_MS} ms."
elif [ "$drops" -eq 0 ] && [ "$over_deadman" -eq 0 ]; then
    echo "verdict  no drops, but ${over_notable} stalls over ${NOTABLE_MS} ms — the robot feels sticky here,"
    echo "         and none of them was long enough for the deadman to stop it."
else
    echo "verdict  the link is not holding: ${drops} drops, ${over_deadman} stalls past the deadman."
    echo "         Each one stops the robot. The kernel lines below name why."
fi

# What padd cannot know: whether the pad left, or the radio did.
if command -v journalctl >/dev/null 2>&1 && { [ "$drops" -gt 0 ] || [ "$over_deadman" -gt 0 ]; }; then
    kernel="$(journalctl -k --since "-$(awk -v cs="$window_cs" 'BEGIN { printf "%d", cs / 100 + 5 }')s" \
        --no-pager 2>/dev/null | grep -iE 'hci|bluetooth' || true)"
    if [ -n "$kernel" ]; then
        echo
        echo "kernel, this window (0x08 = supervision timeout: range or interference;"
        echo "                     0x13/0x16 = the pad was switched off, which is not a fault)"
        printf '%s\n' "$kernel" | tail -20
    fi
fi
