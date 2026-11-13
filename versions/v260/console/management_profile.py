"""Published R17 management capabilities and action metadata."""
import json
from pathlib import Path

# The warm SSH channel injects the same descriptor instead of copying files.
PROFILE=globals().get('PROFILE') or json.loads(Path(__file__).with_name('management-profile.json').read_text(encoding='utf-8'))
DEFAULTS=PROFILE['defaults']
SLOTS=tuple(row['slot'] for row in PROFILE['actions'])
LABELS={row['slot']:row['label'] for row in PROFILE['actions']}
ACTION_INFO={row['slot']:row for row in PROFILE['actions']}

def legacy_builds(first,last=22):
    if first>last:return frozenset()
    return frozenset(f'590b986-feetech-ft6-control.{n}' for n in range(first,last+1))|{'590b986-feetech-ft6-control.14.1'}

def supports_feature(report,feature):
    explicit=report.get('management_capabilities')
    if isinstance(explicit,dict) and feature in explicit:return explicit[feature] is True
    build=str(report.get('build',''))
    # The native FT6 family exposes these routes. A new revision is not a new
    # permission gate: unavailable methods still return their actual IPC error.
    if '-feetech-ft6-control.' in build and not build.startswith('590b986-'):
        return feature in PROFILE['features']
    if feature in PROFILE.get('legacy_builds',{}):
        return build in {f'590b986-feetech-ft6-control.{n}' for n in PROFILE['legacy_builds'][feature]}
    return build in legacy_builds(PROFILE['legacy_first'].get(feature,100))
