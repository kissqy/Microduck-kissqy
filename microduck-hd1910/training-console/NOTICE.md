# Source and license notices

This application is a local orchestration/UI layer for the official Microduck training code. It does not include, replace, or flash robot firmware.

- Official training: https://github.com/pollen-robotics/microduck_rl at 8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec. Installed separately by the environment setup command with its original source files and locked dependencies. Serialized task/model reference values are derived from this revision. The upstream Apache 2.0 license is included at docs/licenses/microduck_rl-Apache-2.0.txt.
- Official runtime protocol: https://github.com/pollen-robotics/microduck at daemon-v0.15.1 / 1fa84386f07884e27866411bc1ba166977bced95. Joint order, Home, policy slots, schema 2 and command encodings are checked against this source. No runtime binaries are bundled.
- HD1910 BAM parameters and target-state reset adaptation: https://github.com/fanhao375/microduck-replica at 25791f0bd260fd869ed841578785fa8d7e14396d, software/training/src/mjlab_microduck/robot/hd1910/1910_m6.json and actuator/feetech_bam.py. The parameter JSON is preserved byte-for-byte as training/hd1910_m6.json. The local actuator inherits the canonical official FrictionDRBamActuator, preserving official friction randomization. No legacy training engine is imported or installed. The donor repository notices and its training Apache 2.0 license are retained in docs/licenses/. The upstream parameter label "sts3215" is preserved; it does not establish a new measurement of this user's physical servos.
- XL330 manufacturer reference values: https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/. Reference only; not hardware settings for HD1910.
- Bundled tomli provides Python 3.10 TOML parsing. Its original MIT license remains at training/_vendor/tomli/LICENSE.

The 820g mass closure is a user-specified physical adaptation. Inertia scales with each body's added mass while its CoM is retained; this is an approximation, not a measured inertia tensor.

R1.5.2 adds a user-requested local schedule adapter: timed curriculum thresholds and default budgets are aligned to the sample count of 4096 environments with 24 steps per iteration. It changes runtime config copies, not the upstream source files, stage values, physics or PPO/BC algorithms. This is a console feature, not an upstream claim that sample-equivalent schedules produce identical policies. Additional checkpoint metadata preserves cumulative samples when resuming with another parallel count.
