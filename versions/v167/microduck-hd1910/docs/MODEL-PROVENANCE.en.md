[简体中文](MODEL-PROVENANCE.md) | **English**

# HD1910 motion models: provenance and distribution scope

This page identifies the author's training results, distributed copies and supporting records per weight file. See [Software and self-trained model rights](SOFTWARE-MODEL-RIGHTS.en.md) and the [Personal Non-Commercial License](../LICENSES/Personal-NonCommercial.txt).

The author confirms that this project's Feetech HD1910 motion policies were trained and adapted by the author. “Self-trained” describes that training contribution; it does not transfer ownership of upstream training software, tasks, geometry or another party's pretrained weights. The project's declared scope for model results and original records the author legally holds and can license separately is personal non-commercial use. Third-party rights and previously valid grants remain intact.

Audit baseline: 2026-10-27, repository commit `ad45dd78d9033ac575d5a92e46342ab0829bb274`, R17 V167 / control.43 package records. Short IDs below are the first 12 characters of the ONNX SHA-256 recorded in each manifest; consult the linked manifest for the full value. Existing binary release archives were not re-extracted, rehashed or modified during this review.

## 1. Ten models listed for the current package

Sources: [package README](../firmware/packaging/README.en.md), [installation inventory](../firmware/packaging/install-files.json), and [V167 ARM64/QEMU format and first-inference report](../firmware/console/verification/v167/arm64-models.json). QEMU checks do not establish real-robot validation for every action.

| Action / distributed name | Short ID | Relative weight location in the package / source record | Recorded checkpoint |
| --- | --- | --- | --- |
| Walking, zero-command hold and recovery `walk` | `1cbf8730eadd` | `models/1cbf8730eadd75a5704332c9f3c10f60/policy.onnx` · [manifest](../firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/manifest.json) | 9599 |
| Sit/stand `sitstand` | `1c94934c6421` | `models/1c94934c6421ec72ed48079cea749668/policy.onnx` · [manifest](../firmware/packaging/models/1c94934c6421ec72ed48079cea749668/manifest.json) | 10000 |
| Ground pick `ground_pick` | `b14e3a8b56dd` | `models/b14e3a8b56ddbb8d2d831e727774a168/policy.onnx` · [manifest](../firmware/packaging/models/b14e3a8b56ddbb8d2d831e727774a168/manifest.json) | 9999 |
| Roulade `roulade` | `59e15d7b04d0` | `models/59e15d7b04d0c40e9b11b8a70bdecae6/policy.onnx` · [manifest](../firmware/packaging/models/59e15d7b04d0c40e9b11b8a70bdecae6/manifest.json) | 9999 |
| Right-foot kick `kick_right` | `67ad09d82f48` | `models/67ad09d82f4865d222a7ae06f250cf9f/policy.onnx` · [manifest](../firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/manifest.json) | 9999 |
| Left-foot kick `kick_left` | `ee0376c92704` | `models/ee0376c927044cdece056ba1d3e6eac7/policy.onnx` · [manifest](../firmware/packaging/models/ee0376c927044cdece056ba1d3e6eac7/manifest.json) | 9999 |
| Roller swizzle `roller_swizzle` | `14195135fcaa` | `roller/swizzle/policy.onnx` · [manifest](../firmware/packaging/roller/swizzle/manifest.json) | 9999 |
| Roller crouch `roller_crouch` | `82be20b115d9` | `roller/crouch/policy.onnx` · [manifest](../firmware/packaging/roller/crouch/manifest.json) | 7999 |
| Roller spin `roller_spin` | `621fe9f3ae34` | `roller/spin/policy.onnx` · [manifest](../firmware/packaging/roller/spin/manifest.json) | 7999 |
| Roller stand-up `roller_standup` | `2575b5894bcd` | `roller/standup/policy.onnx` · [manifest](../firmware/packaging/roller/standup/manifest.json) | 11000 |

These comprise six ordinary-foot actions and four roller actions. The current Git tree mainly stores provenance and deployment metadata under `packaging/models/` and `packaging/roller/`; the installation inventory lists weights distributed in the firmware archive. `packaging/LICENSE` already declares Apache-2.0; this page cannot blanket-relicense files already subject to that express grant as non-commercial. Equally, a software directory license alone does not establish the rights chain of every separately distributed weight. Check each weight's accompanying notices, provenance and prior valid grants. This page does not withdraw existing grants or claim to have inspected every license inside historical archives.

## 2. Six policy weights stored directly in the source tree

`firmware/policies/` contains these six `policy.onnx` files. This directory count is not the count of models in the current release. Its `stand` model is a stand-up teacher for training/evaluation, not the current automatic stationary-hold slot; it is absent from the ten-model installation inventory above.

| Source weight | Corresponding ID | Git blob SHA-1 at the audited baseline |
| --- | --- | --- |
| [walk/policy.onnx](../firmware/policies/walk/policy.onnx) | `1cbf8730eadd75a5704332c9f3c10f60` | `cadea39ee4a5253660cf08eced75e473f75a20a4` |
| [sitstand/policy.onnx](../firmware/policies/sitstand/policy.onnx) | `1c94934c6421ec72ed48079cea749668` | `ce482e6dca89d3b53bf54fc4461b14ce20e6c97f` |
| [ground_pick/policy.onnx](../firmware/policies/ground_pick/policy.onnx) | `b14e3a8b56ddbb8d2d831e727774a168` | `dff6e83ce5fcd080113a71d3c55bd56e0ee8d7b0` |
| [roulade/policy.onnx](../firmware/policies/roulade/policy.onnx) | `59e15d7b04d0c40e9b11b8a70bdecae6` | `2cdf8fdb6362a06c344a5bd6e70e9474b93eeef9` |
| [kick_left/policy.onnx](../firmware/policies/kick_left/policy.onnx) | `ee0376c927044cdece056ba1d3e6eac7` | `2b6703c2f6b15326a59180c7e16d8fb3d6da6bc0` |
| [stand/policy.onnx](../firmware/policies/stand/policy.onnx) | `a481d9f211f31d9476ab1a319fe362a2` | `a2adfc893d1125e1fd08836799a6a5bffdfe3020` |

Git blob SHA-1 identifies the audited repository object; it is not the ONNX file's SHA-256. The `a481…` [source record](../firmware/packaging/models/a481d9f211f31d9476ab1a319fe362a2/manifest.json) declares `teacher_only: true` and checkpoint 11000.

## 3. What the existing records establish

Most current action manifests identify upstream training software `pollen-robotics/microduck_rl` at commit `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`, HD1910 adaptation, the task, checkpoint, export hash and a local training run. The older sit/stand record identifies commit `25791f0bd260fd869ed841578785fa8d7e14396d`. A training-code source field does not mean the weights were supplied by upstream, nor does it verify every underlying right.

The `walk` [training-request snapshot](../firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/training-request.json) records resumption, a warm start and two expert/anchor checkpoints. Local cache paths alone do not identify all teachers' original authors, download sources or licenses. Several other snapshots record `resume: false`; that field alone does not prove a complete from-scratch initialization or chain of rights. “Self-trained by the author and adapted for HD1910” is supported by the author's statement and run records; a blanket “all models wholly original from scratch, without third-party weights” is not established by this audit.

For each future model, retain: author, task/version, ONNX SHA-256, training-software commit, from-scratch/resume/fine-tuning/distillation status, initial and teacher weight authors/sources/licenses, original code/configuration changes, data/geometry sources, export record, applicable terms and actual hardware-validation scope. Mark unknown facts explicitly; a timestamp or filename is not provenance evidence.

## 4. Historical models, references and test fixtures

| Scope | Identity and treatment |
| --- | --- |
| `firmware/test-data/walk-teacher14000/` | Historical walking teacher / numeric regression sample, SHA-256 prefix `9e3ff8bde021`, checkpoint 13999; distinct from current `walk` |
| `firmware/test-data/walk-teacher10000/` | Historical HD1910 walking sample, prefix `0b8f04476cab`; absent from the current ten-model installation inventory |
| `firmware/test-data/ground-pick-legacy/`, `roulade-legacy/` | Historical training/regression weights, prefixes `2b69fa681ed0` and `8fdaf12c7478`; confirm the terms applicable to their own provenance |
| `firmware/robotd/test-data/joint-audit/` | Joint-model audit sample, prefix `5c019c3d3d2c`; a test-directory location does not establish upstream ownership or unrestricted use |
| `firmware/verification/official-reference/hf-policies-*.onnx` | Identified upstream reference weights, excluded from the author's self-trained originality claim; confirm the license of each source weight |
| `firmware/duck-control/tests/fixtures/*.onnx` | Shape/state/error-input fixtures, not deployable motion policies |
| `firmware/pet-detect/models/pet_detect.onnx` | Petting-audio classifier, documented as ported from `apirrone/microduck_pet_detect`; not an HD1910 motion policy or claimed original weight |

Neural policy weights are distinct from 3D geometry such as `duck.bin`, `duck-visual.bin` and STL assets. See [third-party credits](THIRD-PARTY.en.md) and the [geometry notice](../firmware/console/licenses/MODEL-NOTICE.md).

## 5. One-legged balance demonstration

The homepage presents the author's self-trained one-legged balance result on a real robot. The reviewed Git tree, ten-model installation inventory and V167 model-check report do not yet identify a separately hashed and sourced weight corresponding to that demonstration. The video therefore does not establish that the current release contains that policy, and cannot replace its license or training-provenance record.

When distributing that weight, give it an individual model directory and provenance record, including any third-party initial or teacher weights. Upstream documentation examples such as `RemiFabre/microduck-flamingo-cycle` have a different source; similarity of an action does not identify them as this project's model or transfer their ownership.
