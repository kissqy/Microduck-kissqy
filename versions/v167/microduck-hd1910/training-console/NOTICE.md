# Source and license notices

Microduck Training Studio is an independent local/SSH training orchestration and user interface. It is not a robot firmware package and does not flash or replace the daemon running on Radxa ZERO.

**Project:** https://github.com/kissqy/Microduck-kissqy

## Software and source references

- **Frozen official training source:** https://github.com/pollen-robotics/microduck_rl at commit `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`. The official environment is installed separately, keeping its source and locked dependencies. Its Apache 2.0 license is retained at `docs/licenses/microduck_rl-Apache-2.0.txt`.
- **Frozen official robot runtime:** https://github.com/pollen-robotics/microduck at commit `1fa84386f07884e27866411bc1ba166977bced95`, release `0.15.1`. The Studio follows the runtime's model and command contract. No runtime daemon binaries are bundled.
- **HD1910 actuator adaptation:** https://github.com/fanhao375/microduck-replica at commit `25791f0bd260fd869ed841578785fa8d7e14396d`, notably `software/training/src/mjlab_microduck/robot/hd1910/1910_m6.json` and `actuator/feetech_bam.py`. The existing parameter data is retained as `training/hd1910_m6.json`; the compatibility actuator uses the official BAM friction randomization infrastructure. Third-party notices and its training license are retained under `docs/licenses/`.
- **XL330 manufacturer reference:** https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/. These figures describe the official hardware reference, not the user's HD1910 settings.
- **Vendored tomli:** MIT license at `training/_vendor/tomli/LICENSE`.

## Interpretation of local hardware values

The Studio's default **820 g** robot mass is a user-specified physical adaptation; its inertia adjustments are approximations rather than a measured full rigid-body inertia tensor. The existing HD1910 BAM data uses an `sts3215` implementation identifier as a compatibility mechanism; showing `HD1910Actuator` in the console does **not** mean a newly identified physical model or a replacement of that implementation.

Task metadata and exported policies record training assumptions and deployment parameters separately. A matching policy interface and successful simulation do not establish equivalent physical performance on different hardware.
