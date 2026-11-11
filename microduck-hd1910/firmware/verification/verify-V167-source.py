#!/usr/bin/env python3
"""Check native source against the retained V164/control.40 snapshot."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/v167'
snapshot=OUT/'v164-native-source.zip'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert sha(snapshot.read_bytes())=='b647f43435f57e70765b6778d82699c7c7ba2a2229f6e664e65b1a3134e3bec0'
record=json.loads((OUT/'source-diff.json').read_text())
def current_bytes(name):
    # Archived baseline names predate consolidation of identical references.
    prefix='verification/official-reference-from146/'
    if name.startswith(prefix):
        name='verification/official-reference/'+name[len(prefix):]
    return (ROOT/name).read_bytes()

def without_redundant_manifest_entries(name, data):
    # Source cleanup only removes these exact duplicate declarations. Keep a
    # byte-level comparison for everything else, especially production Rust.
    if name == 'Cargo.toml':
        return data.replace(b'"duck-ble", "duck-ble", ', b'"duck-ble", ', 1)
    if name == 'duck-control/Cargo.toml':
        return data.replace(b'\n[dev-dependencies]\nserde_json.workspace = true\n', b'', 1)
    if name == 'updater/Cargo.toml':
        prefix, separator, development = data.partition(b'\n[dev-dependencies]\n')
        for duplicate in (
            b'async-trait.workspace = true',
            b'clap = { version = "4.6.4", features = ["derive"] }',
            b'semver.workspace = true',
            b'serde_json.workspace = true',
            b'sha2 = "0.11.0"',
            b'tar = "0.4.46"',
            b'tracing-subscriber = { version = "0.3.23", features = ["env-filter"] }',
            b'zstd = "0.13.3"',
        ):
            development = development.replace(duplicate + b'\n', b'', 1)
        return prefix + separator + development
    return data

with zipfile.ZipFile(snapshot) as z:
    changed=[name for name in z.namelist()
             if without_redundant_manifest_entries(name, z.read(name))
             != without_redundant_manifest_entries(name, current_bytes(name))]
    assert set(changed)=={'duck-control/src/hd1910.rs','duck-control/src/feetech.rs','robotd/src/feetech_commissioning.rs'},changed
    name='duck-control/src/feetech.rs'
    assert z.read(name).split(b'#[cfg(test)]',1)[0]==(ROOT/name).read_bytes().split(b'#[cfg(test)]',1)[0]
    name='robotd/src/feetech_commissioning.rs'
    assert z.read(name).replace(b'control.40',b'control.43')==(ROOT/name).read_bytes()
for name,expected in record['sha256'].items():
    assert sha((ROOT/name).read_bytes())==expected,name
assert not record['added_readback_transactions']
print('V164 native source comparison passed; only fixed settings and build identity change production code')
