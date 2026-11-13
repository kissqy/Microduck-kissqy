# The image `scripts/systemd-test.sh` boots, and the only place in this repository where systemd
# runs as pid 1.
#
# Trixie, unlike `dev-build.Dockerfile`: this one *runs* what a board runs rather than building it,
# so it should be the userland we ship rather than the older one binaries are built against.
#
# `systemd` and `dbus` only. The point is a real init with real cgroups and real transient timers,
# and everything else the update needs — the binaries, the units, the hook — arrives inside the
# signed releases the harness mints, exactly as it does on a board.
FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends systemd dbus \
    && rm -rf /var/lib/apt/lists/*

# systemd's own convention for "stop, cleanly". Without it `docker stop` sends SIGTERM, which pid 1
# systemd reads as a request to re-exec rather than to shut down.
STOPSIGNAL SIGRTMIN+3

# `/lib/systemd/systemd`, because Debian's slim images ship no `/sbin/init` symlink — the harness
# passes it explicitly and this only records why.
CMD ["/lib/systemd/systemd"]
