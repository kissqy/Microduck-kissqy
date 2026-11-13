[简体中文](THIRD-PARTY.md) | **English**

# Third-party sources and licensing scope

This is an attribution index. Complete licenses, copyright headers and NOTICE files remain in their respective directories; this page does not replace them. See [Software and self-trained model rights](SOFTWARE-MODEL-RIGHTS.en.md) for the scope, use and provenance of the author's software and policies.

## Software, dependencies and assets

| Component | Source / license | Repository location |
| --- | --- | --- |
| Microduck Rust firmware workspace and upstream code | Pollen Robotics; Apache-2.0. The workspace containing the Feetech runtime adaptation retains this license independently of personal terms for a UI or model | `firmware/LICENSE`, `firmware/Cargo.toml` |
| Official training engine | Pollen Robotics microduck_rl; software Apache-2.0; downloaded at a pinned commit during first environment preparation, rather than included in the Studio source bundle | `training-console/NOTICE.md`, `training-console/docs/licenses/microduck_rl-Apache-2.0.txt` |
| HD1910 parameters and corresponding actuator implementation | fanhao375/microduck-replica; relevant training code, configuration and parameters Apache-2.0; not exclusively owned by this project | `training-console/docs/licenses/`, `training-console/training/hd1910_m6.json`, `training-console/training/hd1910_actuator.py` |
| Three.js and OrbitControls | Three.js authors; MIT. Copies used by web demos, the assembly viewer and the robot console retain the same attribution and license; local module-path adjustments do not change the license | `firmware/console/static/vendor/`, `firmware/console/licenses/THREE-MIT.txt`; web copies in root `docs/vendor/` |
| ONNX Runtime 1.28.0 | Microsoft and dependency authors; MIT and listed third-party terms | `firmware/packaging/onnxruntime/LICENSE`, adjacent `ThirdPartyNotices.txt` |
| PyYAML | Original authors; MIT | `firmware/packaging/_model_yaml/LICENSE` |
| tomli | Taneli Hukkinen; MIT | `training-console/training/_vendor/tomli/LICENSE` |
| ST IMU and ToF drivers | STMicroelectronics; respective headers and bundled BSD terms | `firmware/firmware/imu-source/vendor/lsm6dsv16x/LICENSE`, `firmware/tof/vendor/LICENSE.txt` |
| Official geometry and display meshes | Pollen Robotics and model contributors; geometry is licensed separately from software, with historical snapshots and current upstream statements checked individually | `firmware/console/licenses/MODEL-NOTICE.md`, `firmware/console/static/assets/duck-visual.json`, and relevant provenance in root `docs/assets/` |
| Official reference ONNX and detection models | Respective upstream model licenses; these are not the author's self-trained weights and are not covered by the author's personal terms | `firmware/verification/official-reference/`, `firmware/pet-detect/`; identify each file from its source record |

Other Rust crates, Python packages and training-environment dependencies retain their own version-specific licenses. This is an index of major recorded sources, not a complete transitive-dependency SBOM. Components downloaded during installation, building or first training setup may still impose redistribution requirements.

## Policies, training software and geometry are different material

Policies resulting from the author's HD1910 training, tuning, selection and validation must be assessed by their particular weights, checkpoints, records and provenance. Using an official engine or task does not mean using official finished weights. Conversely, placing a file in this repository or renaming it does not establish training from scratch or ownership of every right.

The project claims only rights in contributions the author actually owns and can license separately, subject to existing valid licenses. See [Software and self-trained model rights](SOFTWARE-MODEL-RIGHTS.en.md) for scope and confirmed or unresolved provenance. Upstream code, actuator parameters, task implementations, geometry, teachers and initial checkpoints retain their respective rights. Training investment alone does not establish copyright in every set of weights.

The existing `firmware/policies/` license does not automatically cover every file in `firmware/packaging/models/`, `firmware/packaging/roller/`, test data or official references merely because they share a repository. Likewise, the Apache notice in `firmware/packaging/LICENSE` does not turn all bundled weights or geometry into Apache software. Check hashes, original terms, provenance and previously valid grants for each file.

## Official geometry: historical snapshots and current upstream terms

Displayed meshes come from the frozen official commits recorded in `MODEL-NOTICE.md` and asset provenance files. The README cited by those historical records said Creative Commons BY-SA-NC without an explicit version. Preserve those records rather than retroactively changing their version without provenance.

The current official microduck_rl [LICENSE-MODELS.md](https://github.com/pollen-robotics/microduck_rl/blob/develop/LICENSE-MODELS.md) expressly licenses STL files in its specified directories under **CC BY-NC-SA 4.0**; check the listed paths and relevant revision. This does not blanket-license all historical models, community modifications, this repository's geometry or training weights, nor does the software's Apache license replace geometry terms.

## Source, runtime packages and images

Upstream firmware retains the rights granted under Apache-2.0. The scope for the author's consoles, tools and documentation is identified in the [component license index](../LICENSE). Personal terms cannot remove rights already validly granted under Apache, MIT or another applicable license.

Console ZIPs, firmware payloads and system images combine programs, runtime libraries, policies, geometry and system software under their respective terms. Bundled personal terms do not change Apache programs' licenses. New repository documentation does not automatically rewrite licenses or hashes inside existing archives, or revoke earlier valid grants. Redistributors must retain applicable licenses, copyright notices, NOTICE files and modification notices, and satisfy any other requirements of included components.

FT6 IMU source and binaries must also be assessed against their actual provenance, the parent license for `firmware/firmware/imu-source/` and ST driver terms. Personal noncommercial scope for HAT/IMU circuit design material does not automatically change existing software licenses.

## Upstream links

- [Microduck](https://github.com/pollen-robotics/microduck)
- [microduck_rl](https://github.com/pollen-robotics/microduck_rl)
- [microduck-replica](https://github.com/fanhao375/microduck-replica)
- [Apache-2.0 original text](https://www.apache.org/licenses/LICENSE-2.0)
- [OSI definition](https://opensource.org/osd)

Microduck, Pollen Robotics and third-party trademarks remain with their respective owners. This project does not imply official endorsement.
