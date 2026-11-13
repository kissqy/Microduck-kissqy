#!/usr/bin/env python3
"""Restore verified runtime resources omitted from the source checkout."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def obtain(path, expected, url, download):
    if not path.is_file():
        if not download:
            raise ValueError(f'Missing {path}; provide the archive or use --download.')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.part')
        try:
            print('Downloading:', path.name, flush=True)
            with urllib.request.urlopen(url, timeout=45) as source, temporary.open('wb') as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            if digest(temporary) != expected:
                raise ValueError('Downloaded SHA256 mismatch: ' + path.name)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if digest(path) != expected:
        raise ValueError('SHA256 mismatch: ' + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--check', action='store_true', help='Check inputs without extracting runtime resources')
    parser.add_argument('--download', action='store_true', help='Download missing pinned archives and verify SHA256')
    args = parser.parse_args()
    layout = json.loads((ROOT / 'SOURCE-LAYOUT.json').read_text(encoding='utf-8'))
    firmware = args.firmware or ROOT / layout['firmware']['local_path']
    base = args.base or ROOT / layout['baseline']['local_path']
    obtain(firmware, layout['firmware']['sha256'], layout['firmware']['url'], args.download)
    obtain(base, layout['baseline']['sha256'], layout['baseline']['url'], args.download)
    if args.check:
        print('Pinned firmware and V164 baseline checksums passed; no resources extracted.')
        return
    with tarfile.open(firmware) as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        resources = layout['materialized_files']
        # Validate every selected member before writing any resource.
        verified = []
        for row in resources:
            relative = PurePosixPath(row['path'])
            if relative.is_absolute() or '..' in relative.parts or not row['path'].startswith('packaging/'):
                raise ValueError('Invalid resource path: ' + row['path'])
            if row.get('source_path'):
                source = PurePosixPath(row['source_path'])
                if source.is_absolute() or '..' in source.parts or not row['source_path'].startswith('policies/'):
                    raise ValueError('Invalid canonical source path: ' + row['source_path'])
                data = (ROOT / row['source_path']).read_bytes()
            else:
                member = members['Microduck-Robotd-FT6-R17/' + row['path'][len('packaging/'):]]
                data = archive.extractfile(member).read()
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Firmware resource mismatch: ' + row['path'])
            verified.append((ROOT / row['path'], data, row['mode']))
        for destination, data, mode in verified:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.is_file() and destination.read_bytes() == data:
                continue
            if destination.is_symlink():
                raise ValueError('Refusing to overwrite a symlink: ' + str(destination))
            destination.write_bytes(data)
            destination.chmod(mode)
    print(f'Restored {len(verified)} verified runtime resources; Git ignores these generated copies.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        raise SystemExit('Preparation failed: ' + str(error))
