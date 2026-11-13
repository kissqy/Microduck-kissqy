[简体中文](SOFTWARE-MODEL-RIGHTS.md) | **English**

# Software and self-trained motion policies: ownership and licensing

“Author” refers to maintainer **kissqy** and the relevant holders of original contributions; their respective attribution remains.

This project trains, adapts and tests motion policies for **Feetech HD1910** hardware. Rights in independently created software implementations, task and reward implementations, original configuration expression, deployment adaptations and documentation belong to their respective authors where legally protected. **Models identified as the author's self-trained results, and accompanying material the author is entitled to license separately, are provided for personal noncommercial use; commercial use requires prior written permission.**

Ordinary builders can use the supplied models without training their own. See the [license scope](../LICENSE) and [Personal Non-Commercial License](../LICENSES/Personal-NonCommercial.txt). Upstream firmware, engines, parameters, drivers and models retain their own licenses.

## Software components and their licenses

| Component and path | Ownership and existing license | Practical effect |
| --- | --- | --- |
| Original Python, JS, CSS, launch and management tools in `firmware/console/` | Separately licensable original work under the [console LICENSE](../firmware/console/LICENSE) | Personal noncommercial use and free sharing subject to notices; organizational use, paid services and distribution with sold products need permission. Third-party assets and firmware payloads are excluded |
| Original UI, orchestration, adaptations and tests in `training-console/` | [Training Studio LICENSE](../training-console/LICENSE) | Does not transfer ownership of the upstream engine, community actuator or users' output models |
| Runtime, Rust workspace and Feetech runtime adaptations in `firmware/` | Existing [firmware LICENSE](../firmware/LICENSE) and workspace declarations remain Apache-2.0, with separately licensed components handled individually | This documentation does not prohibit commercial use of previously Apache-licensed software. Retain licenses, attribution, applicable NOTICE files and modification notices |
| Deployment scripts and configuration in `firmware/packaging/` | Existing [packaging LICENSE](../firmware/packaging/LICENSE) is Apache-2.0; independent weights, dependencies and explicitly scoped assets are separate | Neither exclusive ownership of the entire bundle nor an unrestricted Apache license for every weight follows from the directory name |
| FT6 IMU code in `firmware/firmware/imu-source/` | Existing parent software license and file notices remain; ST drivers have their own terms | The board-design license does not relicense previously published firmware. The author's assembled IMU is already flashed with FT6 |
| Official training engine, community HD1910 parameters and actuator | Upstream terms; [Studio NOTICE](../training-console/NOTICE.md) | Retain pinned sources and attribution. Using a framework does not transfer its copyright or automatically determine the output weights' license |
| Original tutorials, release material, additions in `microduck-hd1910/docs/` and `tools/` | Personal noncommercial terms within the existing [LICENSE scope](../LICENSE) | Excludes third-party excerpts, reference code and expressly licensed material. Technical facts and parameter values do not become exclusive rights |
| Root `docs/` demos, assembly and budget/shopping pages, and `scripts/` | Original UI/tools follow the root [license index](../../LICENSE); shared console code follows its applicable scope, and existing express licenses prevail | Three.js in `docs/vendor/`, upstream reference configurations and geometry are not exclusively owned by the maintainer |
| ONNX Runtime, Three.js, PyYAML, tomli, ST drivers and other dependencies | Their own MIT, BSD, Apache or other terms | See [third-party sources](THIRD-PARTY.en.md); preserve actual dependency notices when building or distributing |

## What “self-trained” means

The author performs HD1910 training, selection, deployment adaptation and real-robot validation. Attribution for that work should be retained. The [model provenance inventory](MODEL-PROVENANCE.en.md) identifies available files, model IDs, source evidence and historical samples. Software, policy weights and robot geometry are distinct licensing subjects.

| Training situation | Treatment |
| --- | --- |
| New weights trained from independent initialization using an upstream framework | Identify the trainer and original contributions; check framework, configuration, input and weight terms separately |
| Resuming, fine-tuning or distilling an existing checkpoint/teacher | Retain its source, license and relationship to the output; additional training does not replace upstream rights |
| Renaming, format conversion, inference scaling or filtering only | Do not describe this alone as new training or complete originality; distinguish deployment changes from training |
| Initialization or teacher provenance absent from records | State “not recorded”; neither presume training from scratch nor deny documented training contributions |
| Models trained by users of this software | The software license does not automatically assign their output to this project's author; assess actual creation, inputs and applicable terms |

Whether particular numerical weights qualify as copyrightable works depends on the applicable law and facts. Training effort or servo adaptation alone does not establish exclusive rights over every parameter, generic motion, algorithm or interface. The project asserts rights and conditions only for material legally held and separately licensable; it does not guarantee independent copyright in every numerical value.

**The one-legged balance demonstration presents the author's training result. No verifiable matching weight package and training-provenance record was located in the current public tree, so it is not represented as a downloadable model among the current ten bundled policies.** An actual release should add its identifier, hashes and provenance.

## Personal use, sharing and commercial use

| Use | Rule |
| --- | --- |
| An individual installs the console/models on their own duck for personal noncommercial learning and training | Allowed within the applicable personal license, without a separate commercial grant |
| Free sharing of covered original source, models or modifications | Keep license text, scope, attribution, third-party notices and change notices; retain the restrictions |
| Preinstallation on sold robots, paid installation/tuning, commercial integration of covered consoles/models | Prior written permission from the relevant holders is required; bundling software “free” with hardware does not remove its conditions |
| Internal use by a company or other organization of personally licensed material | The existing terms also require permission for organizational use, irrespective of charging a fee |
| Separate use, modification or sale of commercially permissive Apache/MIT components | Follow their licenses; this project's author cannot impose a blanket extra permission requirement |
| Commercial distribution of an entire robot | Handle software, weights, board designs and geometry/print files separately. The author cannot grant other holders' rights |

For commercial requests, use the maintainer's contact information on the [repository homepage](https://github.com/kissqy/Microduck-kissqy), identifying versions, files/models, use and distribution. Only rights the maintainer legally holds can be granted. Statutory permissions and previously valid grants are not withdrawn.

## Existing releases and future provenance

This update organizes source-repository and download-page documentation. **It does not rebuild existing ZIPs, firmware payloads or system images, or change program/model bytes.** Check notices actually supplied inside each historical package; this page is not evidence that old archives were repackaged with new documents. Valid existing Apache and other grants remain effective.

Future models should retain an action/model ID, trainer, weight SHA-256, training-code version, initialization method, base/teacher source and license, original-change description, training/export records, deployment contract and applicable license. Mark unavailable fields “not recorded”; a trainer name, iteration count or folder name does not establish the full chain.

## Legal and licensing references

- [PRC Copyright Law](https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html): originality, authorship and rights in adaptations without displacing the original work.
- [Regulations on Computer Software Protection](https://www.cac.gov.cn/2013-02/08/c_126468744.htm): independently developed software/documentation; exclusion of ideas, methods and mathematical concepts from that protection.
- [Apache-2.0 section 4](https://www.apache.org/licenses/LICENSE-2.0): upstream notices and grants remain; separately licensable modifications may have different terms.
- [Supreme People's Court case explanation](https://www.court.gov.cn/zixun/xiangqing/425412.html): original contributions and compliance with upstream licenses are separate questions.

This guide explains component licenses; it creates no exclusivity beyond legal rights and does not describe personal noncommercial terms as an OSI-standard open-source license.
