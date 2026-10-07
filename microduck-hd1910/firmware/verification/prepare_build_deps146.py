"""Unpack real Debian build dependencies locally; never install system packages."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import lzma
import subprocess
import tempfile
import urllib.request

ROOT = Path('/tmp/r17-debian-build-deps')
CACHE = ROOT / 'cache'
HOST = ROOT / 'host'
ARM = ROOT / 'arm64'
MIRROR = 'https://deb.debian.org/debian/'


def fetch(url, path):
    if not path.is_file():
        with urllib.request.urlopen(url, timeout=45) as response:
            path.write_bytes(response.read())
    return path.read_bytes()


def prepare(group):
    suite, arch, names, destination = group
    index_path = CACHE / f'{suite}-{arch}-Packages.xz'
    index_url = f'{MIRROR}dists/{suite}/main/binary-{arch}/Packages.xz'
    raw = fetch(index_url, index_path)
    packages = {}
    for stanza in lzma.decompress(raw).decode().split('\n\n'):
        fields = dict(line.split(': ', 1) for line in stanza.splitlines()
                      if not line.startswith(' ') and ': ' in line)
        if fields.get('Package') in names:
            packages[fields['Package']] = fields
    assert set(packages) == set(names), set(names) - set(packages)
    output = []
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        fields = packages[name]
        url = MIRROR + fields['Filename']
        path = CACHE / Path(fields['Filename']).name
        content = fetch(url, path)
        digest = hashlib.sha256(content).hexdigest()
        assert digest == fields['SHA256'], name
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            subprocess.run(['ar', 'x', str(path.resolve())], cwd=temporary, check=True)
            data = list(Path(temporary).glob('data.tar*'))
            assert len(data) == 1
            subprocess.run(['tar', '-xf', str(data[0]), '-C', str(destination)], check=True)
        output.append(dict(package=name, version=fields['Version'], architecture=arch,
                           url=url, sha256=digest, destination=str(destination)))
    return dict(suite=suite, architecture=arch, index_url=index_url,
                index_sha256=hashlib.sha256(raw).hexdigest(), packages=output)


if __name__ == '__main__':
    CACHE.mkdir(parents=True, exist_ok=True)
    groups = [('bookworm', 'amd64', ['pkgconf-bin', 'libpkgconf3', 'libudev-dev', 'libudev1'], HOST),
              ('bullseye', 'arm64', ['libudev-dev', 'libudev1'], ARM)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(prepare, groups))
    tool = Path('/tmp/r17-native-tools/bin/pkg-config')
    if not tool.exists():
        tool.symlink_to(HOST / 'usr/bin/pkgconf')
    report = dict(host=str(HOST), arm64=str(ARM), groups=results)
    Path(__file__).with_name('native-dependencies146.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
