#!/usr/bin/env python3
"""Development-only full-resolution visual export (requires numpy).

Uses official STL surfaces with the unmodified 590b986 kinematic tree. No
decimation, invented jaw hinge, controller changes, or runtime dependencies.
"""
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from telemetry import BASELINE, NAMES

ROOT = Path(__file__).resolve().parent
MODEL_REVISION = 'e8a2de510b6cb5062e9ccab8b41f2d47f2186504'
HIDDEN = {'np_f970', 'pcb__raspberry_pi_zero_2_w', 'elec_rpi_robot_hat_pcb',
          'power_support', 'banana_pcb_locker', 'motor_support'}


def values(element, key, default):
    return np.array([float(v) for v in element.get(key, default).split()])


def qmul(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return np.array([w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j,
                     w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v])


def rotate(q, p):
    return qmul(qmul(q, np.r_[0, p]), q*np.array([1, -1, -1, -1]))[1:]


def frozen_bodies(data):
    magic, version, nm, nb, nparts = struct.unpack_from('<4sIHHH', data)
    if magic != b'DUCK' or version != 1:
        raise ValueError('Expected the frozen terminal asset')
    p = 14
    for _ in range(nm):
        nv, nt = struct.unpack_from('<HH', data, p)
        p += 4 + nv*12 + nt*6
    body_bytes = data[p:p+44*nb]
    bodies = [struct.unpack_from('<hh10f', body_bytes, i*44) for i in range(nb)]
    return body_bytes, bodies


def full_mesh(path):
    raw = path.read_bytes()
    nt, = struct.unpack_from('<I', raw, 80)
    if len(raw) != 84 + nt*50:
        raise ValueError(f'Invalid binary STL: {path}')
    records = np.frombuffer(raw, dtype=np.uint8, offset=84).reshape(nt, 50)
    triangles = records[:, 12:48].copy().view('<f4').reshape(nt, 3, 3)
    if not np.isfinite(triangles).all():
        raise ValueError(f'Invalid coordinates: {path}')
    corners = triangles.reshape(-1, 3)
    vertices, ids = np.unique(corners, axis=0, return_inverse=True)
    face_normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]).astype(np.float64)
    lengths = np.linalg.norm(face_normals, axis=1)
    unit = face_normals / np.maximum(lengths[:, None], 1e-30)
    # Average normals only within a 35-degree surface crease. This smooths the
    # original CAD curves while retaining sharp shell edges and servo corners.
    order = np.argsort(ids, kind='stable')
    bounds = np.r_[0, np.flatnonzero(np.diff(ids[order]))+1, len(order)]
    normals = np.empty_like(corners)
    cutoff = np.cos(np.deg2rad(35))
    for a, b in zip(bounds[:-1], bounds[1:]):
        ci = order[a:b]
        fi = ci//3
        near = unit[fi] @ unit[fi].T >= cutoff
        average = near @ face_normals[fi]
        average /= np.maximum(np.linalg.norm(average, axis=1)[:, None], 1e-30)
        normals[ci] = average
    # Split vertices at sharp normal boundaries, preserving every original
    # triangle and its winding. Only equivalent vertex records are welded.
    combined = np.concatenate([corners, np.round(normals, 6)], axis=1)
    records, faces = np.unique(combined, axis=0, return_inverse=True)
    pos = records[:, :3].astype('<f4')
    normal = records[:, 3:].astype('<f4')
    index = faces.astype('<u4')
    return pos, normal, index, hashlib.sha256(raw).hexdigest()


def build(mjcf, output):
    frozen_path = ROOT/'static/assets/duck.bin'
    frozen = frozen_path.read_bytes()
    frozen_hash = hashlib.sha256(frozen).hexdigest()
    if frozen_hash != '1e1200053e2326706632306bc80831d5e0dfa5462d792a677fc05a43f145651e':
        raise ValueError('Frozen baseline model changed')
    body_bytes, bodies = frozen_bodies(frozen)
    tree = ET.parse(mjcf).getroot()
    materials = {m.get('name'): values(m, 'rgba', '.5 .5 .5 1')[:3] for m in tree.iter('material')}
    mesh_dir = mjcf.parent/tree.find('compiler').get('meshdir', '.')
    mesh_files = {m.get('name') or Path(m.get('file')).stem: m.get('file') for m in tree.findall('asset/mesh')}
    by_joint = {b[1]: i for i, b in enumerate(bodies)}
    meshes, parts, source_hashes, frame_corrections = {}, [], {}, {}
    max_offset = 0.0

    def walk(body, parent):
        nonlocal max_offset
        joint = body.find('joint')
        jid = NAMES.index(joint.get('name')) if joint is not None else -1
        bi = by_joint[jid]
        frozen_body = bodies[bi]
        if frozen_body[0] != parent:
            raise ValueError('Source kinematic hierarchy differs from 590b986')
        source_q = values(body, 'quat', '1 0 0 0')
        target_q = np.array(frozen_body[5:9])
        source_q /= np.linalg.norm(source_q)
        target_q /= np.linalg.norm(target_q)
        correction = qmul(target_q*np.array([1, -1, -1, -1]), source_q)
        axis = values(joint, 'axis', '0 0 1') if joint is not None else np.zeros(3)
        if not np.allclose(axis, frozen_body[9:12], atol=1e-7):
            raise ValueError('Source joint axis differs from 590b986')
        if abs(np.dot(source_q, target_q)) < 1-1e-8:
            # The RL right ankle local frame is rotated 180 degrees about its
            # own hinge. Rebase its attached visuals into the frozen frame.
            # Axis invariance guarantees this correction commutes with the
            # measured joint rotation for every angle, not just the home pose.
            if body.findall('body') or not np.allclose(rotate(correction, axis), axis, atol=1e-7):
                raise ValueError('Source frame cannot be rebased without changing kinematics')
            frame_corrections[NAMES[jid]] = correction.tolist()
        offset = np.max(np.abs(values(body, 'pos', '0 0 0')-frozen_body[2:5]))
        max_offset = max(max_offset, float(offset))
        if offset > .00005:
            raise ValueError('Source rest position differs by more than 0.05 mm')
        for geom in body.findall('geom'):
            if geom.get('class') != 'visual' or geom.get('type') != 'mesh':
                continue
            name = geom.get('mesh')
            if name in HIDDEN:
                continue
            if name not in meshes:
                pos, normal, index, sha = full_mesh(mesh_dir/mesh_files[name])
                meshes[name] = (pos, normal, index)
                source_hashes[name] = sha
            rgb = np.rint(np.clip(materials[geom.get('material')], 0, 1)*255).astype(int)
            parts.append((bi, list(meshes).index(name), *rgb, 0,
                          *rotate(correction, values(geom, 'pos', '0 0 0')),
                          *qmul(correction, values(geom, 'quat', '1 0 0 0'))))
        for child in body.findall('body'):
            walk(child, bi)

    for body in tree.find('worldbody').findall('body'):
        walk(body, -1)
    data = bytearray(struct.pack('<4sIHHHH', b'DUCK', 2, len(meshes), len(bodies), len(parts), 0))
    for pos, normal, index in meshes.values():
        data.extend(struct.pack('<II', len(pos), len(index)//3))
        data.extend(pos.tobytes()); data.extend(normal.tobytes()); data.extend(index.tobytes())
    data.extend(body_bytes)  # byte-identical frozen joint frames
    for p in parts:
        data.extend(struct.pack('<HH4B7f', *p))
    output.write_bytes(data)
    counts = [len(m[2])//3 for m in meshes.values()]
    manifest = {'format': 'DUCK/2', 'runtime_baseline': BASELINE,
                'visual_repository': 'https://github.com/pollen-robotics/microduck_rl',
                'visual_revision': MODEL_REVISION, 'frozen_skeleton_sha256': hashlib.sha256(body_bytes).hexdigest(),
                'geometry_sha256': hashlib.sha256(data).hexdigest(),
                'source_xml_sha256': hashlib.sha256(mjcf.read_bytes()).hexdigest(),
                'source_mesh_sha256': source_hashes, 'meshes': len(meshes), 'bodies': len(bodies),
                'parts': len(parts), 'unique_triangles': sum(counts),
                'drawn_triangles': sum(counts[p[1]] for p in parts),
                'source_frame_max_difference_mm': max_offset*1000,
                'visual_frame_corrections_wxyz': frame_corrections,
                'frame_policy': 'All joint frames use byte-identical 590b986 bodies; visual STL placement is from the pinned RL model.',
                'changes': 'No decimation; crease-aware display normals; hidden electronics omitted; mouth remains fixed.'}
    output.with_suffix('.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('source_mesh_sha256',)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mjcf', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'static/assets/duck-visual.bin')
    args = parser.parse_args()
    build(args.mjcf, args.output)
