#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# USB quirk handling adapted from Armbian (https://www.armbian.com/authors):
# https://github.com/armbian/build/blob/main/packages/bsp/common/usr/lib/armbian/armbian-hardware-optimization
# Armbian's function is licensed under GPL version 2, without warranty.
"""Repair the known Armbian 26.2.1 boot-config writer without upgrading the OS."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

TARGET = Path('/usr/lib/armbian/armbian-hardware-optimization')
BOOT_ENV = Path('/boot/armbianEnv.txt')
BACKUPS = Path('/var/backups/microduck-armbian-env')
FUNCTION = re.compile(r'^add_usb_storage_quirks\(\) [({]\n.*?^[})] # add_usb_storage_quirks$', re.M | re.S)
LEGACY_SHA256 = '25545def5d725e7cf613117a7b1d68667ad3188fbe24fab9dead9e96fed2fd82'
REPLACEMENT = r'''
add_usb_storage_quirks() (
	# Local fix: do not rewrite boot configuration unless its contents change.
	# Keep temporary work in /tmp (tmpfs on this board), off the boot filesystem.
	set -o pipefail
	ENVFILE=/boot/armbianEnv.txt
	[ -f "$ENVFILE" ] || return 0
	[ -s "$ENVFILE" ] || return 1
	WORKDIR=$(mktemp -d /tmp/armbian-usb-quirks.XXXXXX) || return 1
	NEWENV=
	trap 'rm -rf -- "$WORKDIR"; if [ -n "$NEWENV" ]; then rm -f -- "$NEWENV"; fi' EXIT
	trap 'exit 1' HUP INT TERM

	# Preserve the existing blacklist and the original USB compatibility rules.
	awk -F"=" '/^usbstoragequirks/ {print $2}' "$ENVFILE" |
		tr -d -c '[:graph:]' > "$WORKDIR/quirks" || return 1
	if [ ! -s "$WORKDIR/quirks" ]; then
		printf '%s\n' '0x2537:0x1066:u,0x2537:0x1068:u' > "$WORKDIR/quirks" || return 1
	fi
	lsusb | awk '{print "0x"$6}' | sed 's/:/:0x/' | sort -u | while read -r DEVICE; do
		case "$DEVICE" in
			0x0bc2:* | 0x1058:*)
				if ! grep -Fq "$DEVICE" "$WORKDIR/quirks"; then
					sed -i "1 s/\$/,${DEVICE}:u/" "$WORKDIR/quirks" || exit 1
				fi
				;;
		esac
	done || return 1
	USBQUIRKS=$(cat "$WORKDIR/quirks") || return 1
	sed -e '/^$/d' -e '/^usbstoragequirks/d' "$ENVFILE" > "$WORKDIR/env" || return 1
	printf 'usbstoragequirks=%s\n' "$USBQUIRKS" >> "$WORKDIR/env" || return 1

	cmp -s "$WORKDIR/env" "$ENVFILE"
	COMPARE_STATUS=$?
	[ "$COMPARE_STATUS" -le 1 ] || return 1
	if [ "$COMPARE_STATUS" -eq 1 ]; then
		# Stage on the same filesystem, preserve metadata, and persist before rename.
		NEWENV=$(mktemp "${ENVFILE%/*}/.armbianEnv.txt.XXXXXX") || return 1
		cat "$WORKDIR/env" > "$NEWENV" || return 1
		chown --reference="$ENVFILE" "$NEWENV" || return 1
		chmod --reference="$ENVFILE" "$NEWENV" || return 1
		sync -- "$NEWENV" || return 1
		mv -fT -- "$NEWENV" "$ENVFILE" || return 1
		NEWENV=
		# Commit the rename as well; U-Boot does not replay the ext4 journal.
		sync -f -- "$ENVFILE" || return 1
	fi

	if [ -f /sys/module/usb_storage/parameters/quirks ]; then
		printf '%s\n' "$USBQUIRKS" > /sys/module/usb_storage/parameters/quirks || return 1
	fi
) # add_usb_storage_quirks
'''.strip()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def patched_script(data):
    """Recognize the vulnerable function, not unrelated board-specific setup."""
    source = data.decode('utf-8')
    matches = list(FUNCTION.finditer(source))
    if len(matches) != 1:
        raise ValueError('Unrecognized USB quirk function; no files changed')
    match = matches[0]
    call = re.compile(r'^([ \t]*)add_usb_storage_quirks(?: &| \|\| exit \$\?)?[ \t]*$', re.M)
    calls = list(call.finditer(source))
    if len(calls) != 1:
        raise ValueError('Unrecognized USB quirk invocation; no files changed')
    if match[0] != REPLACEMENT and sha256(match[0].encode()) != LEGACY_SHA256:
        raise ValueError('Unknown or upstream-modified USB function; review it before applying this fix')
    source = source[:match.start()] + REPLACEMENT + source[match.end():]
    return call.sub(r'\1add_usb_storage_quirks || exit $?', source).encode()


def fsync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_filesystem(path):
    # Commit the rename's filesystem transaction for boot readers without replay.
    subprocess.run(['sync', '-f', str(path)], check=True)


def atomic_write(path, data, metadata):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            current = os.fstat(stream.fileno())
            if (current.st_uid, current.st_gid) != (metadata.st_uid, metadata.st_gid):
                os.fchown(stream.fileno(), metadata.st_uid, metadata.st_gid)
            os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
        sync_filesystem(path)
    finally:
        temporary.unlink(missing_ok=True)


def regular_file(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Expected a regular file, not a symlink: ' + str(path))


def repair(target=TARGET, boot_env=BOOT_ENV, backups=BACKUPS, apply=False):
    if not target.exists():
        return {'status': 'not-applicable', 'detail': 'Armbian hardware optimization script absent'}
    regular_file(target)
    original = target.read_bytes()
    updated = patched_script(original)
    if original == updated:
        if apply:
            # Retry a previous invocation whose final filesystem sync failed.
            sync_filesystem(target)
        return {'status': 'already-fixed', 'sha256': sha256(updated)}
    if not apply:
        return {'status': 'needs-fix', 'sha256': sha256(original)}
    regular_file(boot_env)
    config = boot_env.read_bytes()
    if not config.strip():
        raise ValueError('Boot configuration is empty; recover it before applying this fix')
    metadata = target.stat()
    # Syntax-check without sourcing the script or running any hardware setup.
    subprocess.run(['bash', '-n'], input=updated, check=True)
    backups.mkdir(mode=0o700, parents=True, exist_ok=True)
    fsync_directory(backups.parent)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')
    backup = Path(tempfile.mkdtemp(prefix=name, dir=backups))
    atomic_write(backup / target.name, original, metadata)
    atomic_write(backup / boot_env.name, config, boot_env.stat())
    manifest = {'target': str(target), 'original_sha256': sha256(original),
                'patched_sha256': sha256(updated), 'boot_env_sha256': sha256(config)}
    atomic_write(backup / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode(), metadata)
    fsync_directory(backups)
    sync_filesystem(backups)
    if target.read_bytes() != original or boot_env.read_bytes() != config:
        raise ValueError('Files changed during backup; not replacing the installed script')
    atomic_write(target, updated, metadata)
    return {'status': 'fixed', 'backup': str(backup), 'sha256': sha256(updated)}


def restore(backup, target=TARGET):
    """Never roll back over a later vendor update or an unrelated backup."""
    regular_file(target)
    manifest = json.loads((backup / 'manifest.json').read_text())
    saved = backup / target.name
    regular_file(saved)
    original = saved.read_bytes()
    current = target.read_bytes()
    if (manifest['target'] != str(target) or sha256(original) != manifest['original_sha256']
            or sha256(patched_script(original)) != manifest['patched_sha256']):
        raise ValueError('Backup does not match this repair')
    if current == original:
        sync_filesystem(target)
        return {'status': 'already-restored'}
    if sha256(current) != manifest['patched_sha256']:
        raise ValueError('Installed script has changed since repair; refusing to overwrite it')
    subprocess.run(['bash', '-n'], input=original, check=True)
    atomic_write(target, original, saved.stat())
    return {'status': 'restored', 'sha256': sha256(original)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--check', action='store_true', help='inspect only (default)')
    action.add_argument('--apply', action='store_true', help='back up and patch the known writer')
    action.add_argument('--restore', type=Path, metavar='BACKUP', help='restore only the saved script')
    args = parser.parse_args()
    if args.apply or args.restore:
        if os.geteuid() != 0:
            parser.error('run --apply/--restore with sudo on the board')
        # Serialize this tool's repairs/restores without locking a replaced inode.
        with open('/run/lock/microduck-armbian-env.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = restore(args.restore) if args.restore else repair(apply=True)
    else:
        result = repair()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('armbian-env repair: ' + str(error), file=sys.stderr)
        sys.exit(1)
