#!/bin/sh
# Install the GStreamer stack `mediad` needs, and report what this board can actually encode.
#
# Split from `setup-board.sh` for the reasons `migrate-network.sh` is split from it — lifetime
# and risk are different:
#
#  1. **Different lifetime.** The overlay fix and the ONNX install in `setup-board.sh` are
#     what makes a board a robot: without them there is no motor bus and no policy. GStreamer
#     is what makes it a *camera*. That was a cost with no payer while nothing used it; `mediad`
#     ships now, so the callers are provisioning (`provision.sh`, on by default) and the
#     updater's pre-install hook, which runs this script out of the release on every apply —
#     which is how a board provisioned before this existed gets the stack without anybody
#     remembering a command.
#  2. **Different question.** Everything in `setup-board.sh` either works or fails. Half of
#     this script's value is the report at the end, which answers a question nothing else on
#     the board answers: *can this kernel encode H.264 in hardware, and through which
#     element*. That decides whether `mediad` streams video at a usable frame rate or cooks
#     the CPU `robotd`'s control loop runs on, and it is worth being able to ask repeatably on
#     any board rather than once, by hand, in a bring-up session nobody wrote down.
#
#   sudo sh /tmp/setup-gstreamer.sh
#   sudo /usr/local/sbin/robot-setup-gstreamer          # later, to re-check
#
# Full paths, because this advice gets copy-pasted and /tmp does not survive a reboot. The
# first run leaves a copy at the second path.
#
# **`hooks/preinstall` runs this too**, from `scripts/setup-gstreamer.sh` in the release, with a
# ten-minute ceiling and no token in its environment — which is why the plugins repository is
# public and why nothing here may prompt. An xtask test keeps the packaging lists in step with
# the hook that runs it.
#
#   --dev     also install the headers and pkg-config files needed to *build* against
#             GStreamer — `gst-plugin-webrtc` on this board, or an aarch64 sysroot to
#             cross-build `mediad` from a laptop. Not wanted on a shipped robot.
#   --help
#
# Idempotent, and safe to re-run: apt is only invoked for packages that are missing, and
# nothing here needs a reboot.
#
# Radxa Zero 3W on Armbian, Debian 13 (trixie) userland. `apt-cache policy` on a provisioned
# board shows GStreamer coming from deb.debian.org and security.debian.org with no Armbian
# multimedia overlay, so these are plain Debian packages at 1.26.x.
set -eu

SELF=/usr/local/sbin/robot-setup-gstreamer

# Whether to install the -dev packages. Off by default: a shipped robot loads plugins, it does
# not compile them, and the headers are the larger half of the install.
WANT_DEV=0

# Where a hand-built out-of-tree plugin goes until `mediad` ships its own.
#
# `gst-plugins-rs` — which is what `webrtcsink`/`webrtcsrc` come from — is packaged in **no**
# Debian suite: not trixie, not backports, not sid. So the plugin is either built here or
# shipped inside the daemon release, and until `mediad` exists this is where a manual build
# lands. GStreamer does not scan it by default, hence the GST_PLUGIN_PATH advice in the report.
GST_EXTRA_PLUGIN_DIR=/usr/local/lib/gstreamer-1.0

# The prebuilt plugins, and the release they come from.
#
# `mpph264enc` (hardware H.264 through Rockchip MPP) and `webrtcsink`/`webrtcsrc` are in no Debian
# suite, so they are built in CI — natively on an arm64 runner in a debian:trixie container, which
# is the robot's own userland — and published at:
#
#   https://github.com/pollen-robotics/microduck-gst-plugins
#
# **A pinned version, never "latest".** Two provisioning runs a day apart that produce different
# plugins, with nothing recording which, is an unreproducible media bug waiting to happen. This is
# the same lesson `ONNX_VERSION` in `setup-board.sh` carries, and an xtask test asserts this
# literal matches `[workspace.metadata.gst-plugins]` in Cargo.toml — this script is fetched
# standalone with curl and cannot read the manifest itself.
#
# The repository is public on purpose: the download happens during provisioning and, later, from
# the updater's preinstall hook, which runs with a cleared environment and no token.
PLUGINS_REPO="${PLUGINS_REPO:-pollen-robotics/microduck-gst-plugins}"
PLUGINS_VERSION="${PLUGINS_VERSION:-v3}"

# What the encoder probe looks at. Variables rather than literals for the reason
# `setup-board.sh` makes CMDLINE one: the interesting states of this check are a board that
# has no VPU node and a board on the wrong kernel, and those are exactly the states you least
# want to discover the check is wrong in. As variables they can be pointed at a fixture.
MPP_SERVICE="${MPP_SERVICE:-/dev/mpp_service}"
# Rockchip's 2D accelerator, which `mppenc` uses for format and stride conversion. Same story as
# the VPU node and found the same way: non-root, `RkRgaInit` fails and the encoder logs
# `Try to use uninit rgaCtx=(nil)` followed by pages of `rga call blit fail`.
RGA_DEV="${RGA_DEV:-/dev/rga}"
VIDEO_GLOB="${VIDEO_GLOB:-/dev/video*}"
KERNEL="${KERNEL:-$(uname -r)}"
# Where the VPU udev rule goes. A variable for the same fixture reason as the three above, and
# because a write into it failing must not be how this script ends.
UDEV_RULE_DIR="${UDEV_RULE_DIR:-/etc/udev/rules.d}"

# Runtime packages, and why each one is here rather than "the usual set".
#
#   gstreamer1.0-tools          gst-inspect-1.0 / gst-launch-1.0. The report below *is*
#                               gst-inspect, and a media fault on a robot in someone's house
#                               is diagnosed with what is already installed.
#   gstreamer1.0-plugins-base   videoconvert, videoscale, videorate, opusenc.
#   gstreamer1.0-plugins-good   videoflip, jpegenc, and the video4linux2 plugin — which is
#                               where `v4l2h264enc` lives if this kernel exposes an encoder.
#   gstreamer1.0-plugins-bad    webrtcbin, the DTLS/SRTP elements it needs, h264parse,
#                               rawvideoparse.
#   gstreamer1.0-nice           ICE. webrtcbin negotiates nothing without it.
#   libnice10                   pulled in by the above; named so a partial install is legible
#                               in the report rather than showing up as "webrtcbin hangs".
#   gstreamer1.0-plugins-ugly   x264enc. Software H.264, GPL — the interim encoder until the
#                               hardware path is settled, and the report says plainly when it
#                               is the only one present.
#   v4l-utils                   v4l2-ctl and media-ctl. Not optional for capture on this
#                               board: gstreamer's own v4l2src is handed a 2-buffer pool by
#                               the vendor rkisp driver and requeues too slowly, dropping
#                               every third frame (~20 fps from a 30 fps sensor), so frames
#                               are captured with `v4l2-ctl --stream-mmap` and piped into
#                               gstreamer. Measured on this hardware — see
#                               `microduck_runtime/src/camera.rs:487`.
#
# Deliberately absent:
#
#   gstreamer1.0-libcamera / libcamera-*   libcamera's mainline rkisp1 pipeline handler does
#                               not drive the *vendor* rkisp this board's camera needs, so it
#                               enumerates nothing here. Installing it buys an element that
#                               finds no camera (`microduck_runtime/radxa_setup/setup.md`).
#   gstreamer1.0-plugins-rs     does not exist in Debian. See GST_EXTRA_PLUGIN_DIR above.
#
# **This list is meant to shrink.** It was assembled from what the pipeline in
# `microduck_runtime/src/camera.rs` uses plus what `webrtcbin` needs to negotiate, which is a
# reasoned guess and not a measurement — `mediad` does not exist yet to be profiled against it.
# Re-read it whenever `mediad`'s pipeline changes shape and drop what nothing loads: every
# package here is disk on a robot, an apt dependency during provisioning, and a security update
# somebody has to care about. `gst-inspect-1.0 --plugin` names what a plugin actually provides,
# which is the check to run before defending an entry.
RUNTIME_PKGS="gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
gstreamer1.0-plugins-bad gstreamer1.0-nice libnice10 gstreamer1.0-plugins-ugly v4l-utils"

# Build packages. `libgstreamer-plugins-bad1.0-dev` is the load-bearing one: it carries
# `gstreamer-webrtc-1.0.pc`, which is what both `cargo cinstall -p gst-plugin-webrtc` and
# `mediad`'s `gstreamer-webrtc-sys` pkg-config against. The rest is what a Rust cdylib build
# needs to link at all.
DEV_PKGS="pkg-config build-essential libssl-dev libgstreamer1.0-dev
libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev"

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    # Steps, not rationale. Why this is a separate script is in the header above, for whoever
    # edits it; someone running --help wants to know what to type.
    cat <<'EOF'
Install the GStreamer stack mediad needs, and report what this board can encode.

  sudo sh /tmp/setup-gstreamer.sh          runtime packages, then the report
  sudo sh /tmp/setup-gstreamer.sh --dev    also the headers, to build against GStreamer
  sudo /usr/local/sbin/robot-setup-gstreamer    re-run later, to re-check the report

Idempotent, and needs no reboot. The first run leaves the copy at that third path.
EOF
    exit 0
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --dev)  WANT_DEV=1 ;;
            --help|-h) usage ;;
            *) die "unknown argument: $1
  Run with --help for what this takes." ;;
        esac
        shift
    done
}

check_environment() {
    # No path in the message: whatever the operator just typed is what needs `sudo` in front.
    [ "$(id -u)" = 0 ] || die "run as root — re-run that same command with sudo"

    arch="$(uname -m)"
    [ "$arch" = aarch64 ] || die "this targets aarch64 boards, and this box is ${arch}"

    command -v apt-get >/dev/null 2>&1 \
        || die "no apt-get — this expects a Debian/Armbian userland"
}

# Leave a copy behind, so re-checking after a kernel change does not need a re-fetch.
#
# Same reasoning as `setup-board.sh`: /tmp is wiped, and the encoder question is one you come
# back to — a vendor-kernel upgrade is exactly the event that changes the answer.
persist_self() {
    case "$0" in
        sh|-sh|bash|-bash|/dev/fd/*|/proc/self/fd/*) return 0 ;;
    esac
    [ -f "$0" ] || return 0

    # Already running from the installed copy: copying a file onto itself truncates it.
    if [ "$(readlink -f "$0" 2>/dev/null)" = "$(readlink -f "$SELF" 2>/dev/null)" ]; then
        return 0
    fi

    install -m 0755 "$0" "$SELF" 2>/dev/null \
        || warn "could not copy this script to ${SELF}; re-fetch it to re-run."
}

# Install every package in $* that is not already installed.
#
# `dpkg -s` per package rather than one `apt-get install` for the lot: apt is slow to start on
# this board, and a re-run that has nothing to do should cost nothing. It also means the log
# names exactly what was missing, which is the difference between "gstreamer was already fine"
# and "gstreamer was half installed" when reading a bring-up log after the fact.
install_missing() {
    missing=""
    for pkg in "$@"; do
        dpkg -s "$pkg" >/dev/null 2>&1 || missing="$missing $pkg"
    done
    [ -n "$missing" ] || return 0

    say "installing:$missing"
    apt-get update -qq || true
    # shellcheck disable=SC2086  # word-splitting the package list is the point
    apt-get install -y -qq $missing \
        || die "apt failed installing:$missing
  Nothing here is partially usable — webrtcbin without libnice negotiates nothing, and a
  missing encoder is a stream that never starts. Fix the network or the apt sources and
  re-run; this script is idempotent."
}

# Is GStreamer element $1 registered?
#
# Both the distro plugin path and GST_EXTRA_PLUGIN_DIR are searched, so a hand-built
# webrtcsink is found here exactly when `mediad` would find it with the same variable set.
have_element() {
    GST_PLUGIN_PATH="${GST_EXTRA_PLUGIN_DIR}${GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}" \
        gst-inspect-1.0 "$1" >/dev/null 2>&1
}

# Print "  <name>  <present|absent>", padded, for the report.
element_line() {
    if have_element "$1"; then
        printf '  %-16s present\n' "$1"
    else
        printf '  %-16s absent\n' "$1"
    fi
}

# Everything the encoder question turns on, in one place.
#
# This is the part worth re-running. The three answers, in the order they are worth having:
#
#   v4l2h264enc  the vendor kernel exposes the VPU as a V4L2 M2M encoder. Best case by a
#                distance: the element is in `gstreamer1.0-plugins-good`, already installed
#                above, so hardware encode needs nothing out of tree at all.
#   mpph264enc   only reachable through Rockchip's MPP userspace library plus the
#                `gstreamer-rockchip` plugin, neither of which Debian packages. Real, but it
#                is a library from a third-party repo and a plugin built from source.
#   x264enc      software. Present because it is installed above, and it is not a fallback to
#                be comfortable with: `jpegenc` alone cannot hold 30 fps at 640x480 on this
#                SoC (`microduck_runtime/src/camera.rs:500`), and H.264 costs more per frame
#                than JPEG. It shares four Cortex-A55s with `robotd`'s 50 Hz control loop.
report_encoders() {
    say "encoders"
    for el in v4l2h264enc mpph264enc x264enc vp8enc jpegenc; do
        element_line "$el"
    done

    printf '\n'
    say "kernel and VPU"
    printf '  %-16s %s\n' kernel "$KERNEL"
    case "$KERNEL" in
        *-vendor-rk35xx)
            printf '  %-16s vendor (BSP) — the camera and VPU nodes live here\n' branch ;;
        *)
            printf '  %-16s NOT the vendor kernel\n' branch
            warn "this is not the *-vendor-rk35xx kernel. The mainline rk356x kernels have no
  MIPI-CSI ISP capture driver, so the camera gets no /dev/video capture node, and the VPU
  nodes this section looks for are unlikely to be there either. setup-board.sh installs the
  vendor kernel for the audio codec; a stray 'apt upgrade' can repoint /boot back." ;;
    esac

    if [ -e "$MPP_SERVICE" ]; then
        # Mode and owner, not just presence. "Present" and "usable by a daemon" are different
        # claims, and the gap between them is silent: with the node at 0600 root:root — which is
        # how it arrives — a non-root `mpi_enc_test` writes an empty file and **exits 0**. No
        # error, no log line. Measured on a Zero 3W, and it cost a round trip to find.
        mode="$(stat -c '%a' "$MPP_SERVICE" 2>/dev/null || true)"
        owner="$(stat -c '%U:%G' "$MPP_SERVICE" 2>/dev/null || true)"
        printf '  %-16s present  %s %s\n' "$MPP_SERVICE" "${mode:-?}" "${owner:-?}"
        # The group bit is what a daemon rides in on: `mediad` runs as its own user, like every
        # other daemon here, so it needs group rw rather than root.
        gbit="$(printf '%s' "$mode" | sed 's/.*\(..\)$/\1/' | cut -c1)"
        case "$gbit" in
            6|7) ;;
            *) printf '  %-16s root-only — a non-root mediad cannot open it\n' '' ;;
        esac
    else
        printf '  %-16s absent\n' "$MPP_SERVICE"
    fi

    printf '\n'
    say "V4L2 devices"
    found_dev=0
    found_encoder=0
    # Unquoted: this is a glob to expand, which is why it is not "$VIDEO_GLOB".
    # shellcheck disable=SC2086
    for dev in $VIDEO_GLOB; do
        [ -e "$dev" ] || continue
        found_dev=1
        # `-D` prints Driver Info, including Card type and Device Caps. The caps are what
        # separates a capture node from an encoder: an M2M or Video Output node is one that
        # takes frames *in*, which a camera node never does.
        info="$(v4l2-ctl -d "$dev" -D 2>/dev/null || true)"
        card="$(printf '%s' "$info" \
            | sed -n 's/^[[:space:]]*Card type[[:space:]]*:[[:space:]]*//p' | head -1)"
        caps="$(printf '%s' "$info" | grep -cE 'Video M2M|Video Output' || true)"
        if [ "${caps:-0}" -gt 0 ]; then
            found_encoder=1
            printf '  %-16s %s  [M2M / output — candidate encoder]\n' "$dev" "${card:-?}"
        else
            printf '  %-16s %s\n' "$dev" "${card:-?}"
        fi
    done
    if [ "$found_dev" != 1 ]; then
        printf '  none\n'
        printf '  (an unattached camera looks exactly like this — the rkisp capture nodes\n'
        printf '   appear only once a sensor is probed, so this is not itself a fault)\n'
    fi


    printf '\n'
    say "verdict"

    # Ordered by what is *true*, not by what is interesting. The first branch is the one a
    # working board hits, and it stays short — a report that prints setup instructions to a board
    # that has already done the setup is worse than one that prints nothing, because it reads as
    # "something is still wrong here".
    if have_element mpph264enc; then
        # Which file is answering matters: the distro package and this script's plugin directory
        # can both provide `rockchipmpp`, and which one the registry keeps is not defined.
        provider="$(GST_PLUGIN_PATH="${GST_EXTRA_PLUGIN_DIR}${GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}" \
            gst-inspect-1.0 mpph264enc 2>/dev/null \
            | sed -n 's/^  Filename *//p' | head -1)"
        printf '  Hardware H.264 is available through mpph264enc.\n'
        printf '  %-14s %s\n' provided-by "${provider:-?}"
        if dpkg -s gstreamer1.0-rockchip1 >/dev/null 2>&1; then
            warn "gstreamer1.0-rockchip1 is also installed and provides the same elements from
  /usr/lib. Two copies on the search path is a coin flip apt can change under you:
      sudo dpkg -r gstreamer1.0-rockchip1"
        fi
        cat <<EOF

  Registering is not encoding. One command settles that:

    gst-launch-1.0 videotestsrc num-buffers=60 ! video/x-raw,width=1280,height=720 \\
      ! mpph264enc ! h264parse ! filesink location=/tmp/gst.h264
    gst-launch-1.0 filesrc location=/tmp/gst.h264 ! h264parse ! avdec_h264 ! fakesink

  Four properties are decisions rather than defaults to inherit, all read off the element on a
  board — \`gst-inspect-1.0 mpph264enc\` has the full list:

    profile=baseline      defaults to high; WebRTC's interoperable floor is Constrained
                          Baseline (profile-level-id 42e01f)
    header-mode=each-idr  defaults to first-frame, which puts SPS/PPS in the first frame only,
                          so a peer that joins late or drops it never decodes
    rotation=180          on the alpha, whose camera is mounted upside down. The encoder does
                          it in hardware; videoflip costs a CPU pass per frame
    bps=<target>          rc-mode is already cbr, which is right for a lossy link, but the
                          bitrate should not be left on "auto calculate"

  There is no B-frame property, so the latency budget's no-B-frames requirement holds by
  construction, and the sink pad takes NV12 — which is what the rkisp capture path emits, so
  nothing converts between capture and encode.
EOF
    elif [ -e "$MPP_SERVICE" ]; then
        cat <<EOF
  /dev/mpp_service is present but mpph264enc is not registered. On a Rockchip BSP kernel the
  VPU is reached through MPP rather than as a V4L2 M2M encoder, so the absent v4l2h264enc above
  is the expected shape and not the problem.

  **First check the plugin's own libraries.** It links librockchip_mpp.so.1 and librga.so.2,
  neither of which is in Debian, and a missing one means the plugin fails to load without a word:

    ldd ${GST_EXTRA_PLUGIN_DIR}/libgstrockchipmpp.so | grep "not found"

  Anything listed there is the answer, and re-running this script installs them.

  **Otherwise, suspect the node before the plugin.** An MPP plugin registers its decoders unconditionally
  and *probes MPP* before registering its encoders, so at 0600 root:root the encoders are
  silently omitted from a plugin that contains them — which is what made Radxa's own deb look
  decode-only when it is not. Check the mode printed above; this script installs the udev rule
  that fixes it, and a user needs to be in the \`video\` group:

    sudo usermod -aG video "\$USER"      # then log in again, or: newgrp video

  If the mode is right and it is still missing, the plugins are absent or MPP's userspace is.
  librockchip-mpp1 and librga2 are not in Debian; this script installs the plugins, and MPP's
  own test binary proves the hardware with no GStreamer involved at all:

    R=https://radxa-repo.github.io/bullseye/pool/main
    curl -sL -O \$R/m/mpp/librockchip-mpp1_1.5.0-1_arm64.deb
    curl -sL -O \$R/m/mpp/librockchip-vpu0_1.5.0-1_arm64.deb
    curl -sL -O \$R/m/mpp/rockchip-mpp-demos_1.5.0-1_arm64.deb
    sudo dpkg -i librockchip-mpp1_1.5.0-1_arm64.deb librockchip-vpu0_1.5.0-1_arm64.deb \\
      rockchip-mpp-demos_1.5.0-1_arm64.deb
    sudo mpi_enc_test -w 1280 -h 720 -t 7 -n 60 -o /tmp/out.h264

  All three in one dpkg call — these are direct downloads, so dpkg resolves nothing and
  rockchip-mpp-demos needs librockchip-vpu0 at exactly that version. And check the file size,
  not the exit code: against an unopenable node that test writes nothing and still exits 0.
EOF
    elif have_element v4l2h264enc && [ "$found_encoder" = 1 ]; then
        cat <<EOF
  Hardware H.264 looks reachable through v4l2h264enc, with no out-of-tree anything — which is
  not the shape a Rockchip BSP kernel usually has, so confirm it encodes before believing it:

    gst-launch-1.0 -v videotestsrc num-buffers=60 ! video/x-raw,width=1280,height=720 \\
      ! v4l2h264enc ! h264parse ! fakesink
EOF
    else
        cat <<EOF
  No hardware H.264 path found: no mpph264enc, no v4l2h264enc, no /dev/mpp_service, no M2M
  node. Either this is not the vendor kernel (see above), or the VPU is not exposed by this
  build.

  x264enc is installed and will work, at a cost worth stating: software H.264 on four A55s
  shares the CPU with robotd's control loop, and jpegenc already cannot hold 30 fps at VGA on
  this SoC. Treat it as the interim encoder for bring-up, not the shipping one.
EOF
    fi
}

# Rockchip's MPP and RGA runtime libraries, from Radxa's pool.
#
# **The plugins do not work without these, and the failure is silent.**
# `libgstrockchipmpp.so` links `librockchip_mpp.so.1` and `librga.so.2`; neither is in Debian, in
# any suite. Missing, the plugin fails to dlopen, GStreamer skips it without a word, and
# `mpph264enc` simply does not exist — which looks exactly like the permission trap and is not it.
#
# This was missed until a *clean* board ran the script: the board it was developed against had
# these installed by hand during bring-up, so the gap was invisible there. Worth remembering as a
# class of bug rather than a one-off.
#
# Direct .deb downloads, the same route `microduck_runtime/radxa_setup/setup_rkaiq.sh` uses for
# rkaiq — so `dpkg -i` resolves nothing and both are named explicitly. Versions match what the
# plugins in the release were *built* against; see the release MANIFEST.
MPP_VERSION="${MPP_VERSION:-1.5.0-1}"
RGA_VERSION="${RGA_VERSION:-2.2.0-1}"
RADXA_POOL="${RADXA_POOL:-https://radxa-repo.github.io/bullseye/pool/main}"

install_rockchip_userspace() {
    dpkg -s librockchip-mpp1 >/dev/null 2>&1 \
        && dpkg -s librga2 >/dev/null 2>&1 && return 0

    tmp="$(mktemp -d)"
    say "fetching Rockchip MPP ${MPP_VERSION} and RGA ${RGA_VERSION} (not in Debian)"
    ok=1
    for path in \
        "m/mpp/librockchip-mpp1_${MPP_VERSION}_arm64.deb" \
        "libr/librga/librga2_${RGA_VERSION}_arm64.deb"
    do
        curl -fsSL -o "${tmp}/$(basename "$path")" "${RADXA_POOL}/${path}" || ok=0
    done
    if [ "$ok" = 1 ]; then
        dpkg -i "${tmp}"/*.deb >/dev/null 2>&1 || ok=0
    fi
    rm -rf "$tmp"
    [ "$ok" = 1 ] || warn "could not install Rockchip MPP/RGA from ${RADXA_POOL}.
  Without them mpph264enc cannot register — the plugin is there and fails to load. Everything
  else here is still done; fix the network and re-run."
}

# Install the prebuilt plugins at the pinned version.
#
# Into GST_EXTRA_PLUGIN_DIR rather than the distro's plugin directory, so an `apt` operation can
# never quietly replace or remove them, and so which copy registers is not left to chance when a
# packaged `gstreamer1.0-rockchip1` is also present.
#
# A stamp file records the installed version. Re-running then costs nothing, which matters because
# this script is also the thing you run to *re-check* the report after a kernel change.
install_plugins() {
    stamp="${GST_EXTRA_PLUGIN_DIR}/.version"
    if [ "$(cat "$stamp" 2>/dev/null || true)" = "$PLUGINS_VERSION" ]; then
        say "plugins already at ${PLUGINS_VERSION}"
        return 0
    fi

    name="microduck-gst-plugins-${PLUGINS_VERSION}-aarch64"
    base="https://github.com/${PLUGINS_REPO}/releases/download/${PLUGINS_VERSION}"
    tmp="$(mktemp -d)"

    say "fetching ${name}"
    # Warn rather than die: the packages and the udev rule above are done and still valuable, and
    # the report below will show the elements missing. A hard stop here would also make a network
    # blip look like a broken script.
    if ! curl -fsSL -o "${tmp}/${name}.tar.gz" "${base}/${name}.tar.gz" \
        || ! curl -fsSL -o "${tmp}/${name}.tar.gz.sha256" "${base}/${name}.tar.gz.sha256"; then
        rm -rf "$tmp"
        warn "could not download ${name} from ${base}
  Hardware encoding and webrtcsink will be unavailable; everything else here is done. Check the
  network, or that ${PLUGINS_VERSION} is a released tag of ${PLUGINS_REPO}, and re-run."
        return 0
    fi

    # Verified before anything is unpacked. `sha256sum -c` reads the bare filename out of the
    # sums file, so it has to run from the directory holding the tarball.
    if ! ( cd "$tmp" && sha256sum -c "${name}.tar.gz.sha256" >/dev/null 2>&1 ); then
        rm -rf "$tmp"
        warn "${name}.tar.gz does not match its published sha256 — not unpacking it."
        return 0
    fi

    tar -xzf "${tmp}/${name}.tar.gz" -C "$tmp" || {
        rm -rf "$tmp"
        warn "could not unpack ${name}.tar.gz"
        return 0
    }

    install -d "$GST_EXTRA_PLUGIN_DIR"
    for so in "${tmp}/${name}"/*.so; do
        [ -e "$so" ] || continue
        install -m 0644 "$so" "${GST_EXTRA_PLUGIN_DIR}/$(basename "$so")"
    done
    # The manifest travels with them: it names the upstream repository and commit each plugin was
    # built from, which is what makes a media bug on this board traceable to a specific build.
    [ -f "${tmp}/${name}/MANIFEST" ] \
        && install -m 0644 "${tmp}/${name}/MANIFEST" "${GST_EXTRA_PLUGIN_DIR}/MANIFEST"
    printf '%s\n' "$PLUGINS_VERSION" > "$stamp"
    rm -rf "$tmp"
    say "installed ${name} into ${GST_EXTRA_PLUGIN_DIR}"
}

# Give the VPU node a group, so a non-root `mediad` can open it.
#
# `/dev/mpp_service` arrives as 0600 root:root, and the failure that causes is silent: a non-root
# `mpi_enc_test` against it writes an empty file and exits 0. Every daemon here rides into a
# kernel resource on a supplementary group — `tofd` into `i2c`, `padd` into `input`, `btd` into
# `bluetooth` — so the VPU gets the same treatment.
#
# `video` rather than `robot`: `robot` gates the IPC sockets *we* define, and a kernel device node
# is not ours to redefine. `video` is the distro convention for this device class, so a developer
# with `gst-launch` gets in exactly the way `mediad` does.
#
# Here rather than in `setup-board.sh`, which owns the other udev rule on this board, because this
# script already probes and reports on the node — one place owning one mechanism. A board that
# skips GStreamer has no use for the rule.
configure_vpu_access() {
    # Both nodes, in one rule. `/dev/rga` was missed the first time round and cost a debugging
    # round exactly like the VPU node did — a non-root encoder that finds its element, starts,
    # and then fails inside RGA. Whichever nodes exist get the group; a kernel without one is not
    # an error here.
    nodes=""
    for n in "$MPP_SERVICE" "$RGA_DEV"; do
        [ -e "$n" ] && nodes="$nodes $n"
    done
    [ -n "$nodes" ] || return 0

    if [ ! -d "$UDEV_RULE_DIR" ]; then
        warn "no ${UDEV_RULE_DIR}; cannot give /dev/mpp_service a group.
  A non-root mediad will not be able to open the VPU. Everything else here is still done."
        return 0
    fi

    rule="${UDEV_RULE_DIR}/99-robot-mpp.rules"
    # Matched on the kernel name alone. The node's subsystem is not something to depend on: it is
    # a Rockchip BSP driver, and a match that is wrong about it silently does nothing.
    content='KERNEL=="mpp_service", GROUP="video", MODE="0660"
KERNEL=="rga", GROUP="video", MODE="0660"'

    if [ -f "$rule" ] && [ "$(cat "$rule")" = "$content" ]; then
        say "VPU: udev rule already in place"
    else
        say "VPU: installing the udev rule for mpp_service and rga (group video, 0660)"
        printf '%s\n' "$content" > "$rule"
        chmod 644 "$rule"
    fi

    # Applied now as well as at the next boot — `udevadm` failing is not worth stopping over.
    udevadm control --reload-rules 2>/dev/null || true
    for n in $nodes; do
        udevadm trigger --action=change --name-match="$(basename "$n")" 2>/dev/null || true
    done

    # Verified rather than assumed. `--name-match` is not in every udev, and a rule that did not
    # take is the state this whole function exists to prevent — so if the node is still root-only,
    # set it directly and say so.
    for n in $nodes; do
        [ "$(stat -c '%G' "$n" 2>/dev/null || true)" = root ] || continue
        chgrp video "$n" 2>/dev/null || true
        chmod 0660 "$n" 2>/dev/null || true
        say "VPU: applied the mode on ${n} directly; the rule takes over at the next boot"
    done
}

report_webrtc() {
    say "WebRTC elements"
    element_line webrtcbin
    element_line webrtcsink
    element_line webrtcsrc

    if ! have_element webrtcsink; then
        cat <<EOF

  webrtcsink/webrtcsrc come from gst-plugin-webrtc in gst-plugins-rs, which Debian does not
  package in any suite. Until mediad ships the plugin in its release payload, build it here:

    sudo /usr/local/sbin/robot-setup-gstreamer --dev
    cargo install cargo-c
    git clone https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git && cd gst-plugins-rs
    git checkout 0.14.5
    cargo cinstall -p gst-plugin-webrtc --prefix=/usr/local --release

  0.14.5 or newer, not 0.14.4: the earlier tags miss a webrtcsink deadlock fix between remote
  description and ICE handling that presents as a client spinning forever on "connecting".
  It builds libgstrswebrtc.so; gst-plugin-rsrtp is the sibling plugin the same stack wants.
EOF
    fi
}

report() {
    printf '\n'
    # Line 1 is "gst-inspect-1.0 version 1.26.2"; the last field is the number alone.
    version="$(gst-inspect-1.0 --version 2>/dev/null | head -1 | awk '{print $NF}' || true)"
    say "GStreamer ${version:-version unknown}"
    printf '\n'
    report_webrtc
    printf '\n'
    report_encoders
    printf '\n'
    if [ "$WANT_DEV" = 1 ]; then
        say "build headers installed — pkg-config --modversion gstreamer-webrtc-1.0"
    else
        say "runtime only. Re-run with --dev to install the build headers."
    fi
}

main() {
    parse_args "$@"
    check_environment
    persist_self
    # shellcheck disable=SC2086  # word-splitting the package lists is the point
    install_missing $RUNTIME_PKGS
    # shellcheck disable=SC2086
    [ "$WANT_DEV" = 0 ] || install_missing $DEV_PKGS
    # After the packages, before the report: a udev problem must not be what stops GStreamer
    # installing, and the report should show the board as this run leaves it.
    # Before the plugins: they link against these, and a plugin whose libraries are absent is a
    # plugin that silently does not register.
    install_rockchip_userspace
    install_plugins
    configure_vpu_access
    report
}

# Called on the last line so a truncated download — the real failure mode of `curl | sh` —
# defines functions and then does nothing, rather than running half a setup.
main "$@"
