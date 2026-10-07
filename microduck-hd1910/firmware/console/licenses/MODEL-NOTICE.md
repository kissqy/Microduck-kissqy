# Microduck geometry attribution

Assets: `static/assets/duck-visual.bin` (browser display), `static/assets/duck.bin` (unchanged frozen skeleton reference).

Full-resolution visuals: https://github.com/pollen-robotics/microduck_rl/tree/e8a2de510b6cb5062e9ccab8b41f2d47f2186504/src/mjlab_microduck/robot/microduck

The browser asset is a derivative retaining original STL triangles, with crease-aware display normals, omitted hidden electronics, and the byte-identical frozen runtime kinematic tree. Right-ankle visual coordinates are rebased onto the frozen hinge frame; the welded mouth remains fixed. The 0.0209 mm source neck-frame discrepancy uses the frozen runtime position. No control parameters or policies are changed. Rebuild with `bake_visual.py`; exact sources, hashes and frame transformations are recorded in `static/assets/duck-visual.json`.

Creator/source: Pollen Robotics and Microduck model contributors.

Direct source: https://github.com/pollen-robotics/microduck/blob/590b986bd8c0d50ae02cb3ea2f59c463b6828168/robotctl/assets/duck.bin

Bake provenance: https://github.com/pollen-robotics/microduck/blob/590b986bd8c0d50ae02cb3ea2f59c463b6828168/scripts/bake-duck-mesh.py

Related official model repository and license statement: https://github.com/pollen-robotics/microduck_rl#license

The upstream README separately identifies the 3D model license as Creative Commons BY-SA-NC. The cited statement does not specify a license version. Preserve the upstream attribution, non-commercial and share-alike restrictions; do not treat the software Apache-2.0 license as an unrestricted license to these geometric assets.

Changes to the legacy `duck.bin` asset: none. It is copied byte-for-byte and retained for frame comparisons. It is no longer the displayed mesh. Both assets preserve the model license described above; the generated full-resolution derivative is not relicensed as software.

Legacy `duck.bin` SHA-256: `1e1200053e2326706632306bc80831d5e0dfa5462d792a677fc05a43f145651e`.

This package is a personal debugging integration, not an official Pollen Robotics product or endorsement.
