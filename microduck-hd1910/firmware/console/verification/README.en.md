[简体中文](README.md) | **English** | [Русский](README.ru.md)

# R147 verification records

`3d-audit147.json` records scope, numerical tests, original hashes, and acceptance limits. `r146_*` contains independent comparisons with the R146 view. All model-direction checks use production Three.js and DuckView without connected servos.

After installing Node.js, open a terminal in the console directory and repeat:

```bash
node verification/test_calibration_reference.mjs
node verification/test_calibration_reference.mjs verification/reference_training_8d0db749.xml
node verification/test_pose_state.mjs
```

The first uses the built-in runtime model, the second training XML from pinned commit 8 d 0 db 749, and the third checks feedback order, missing values, old targets, and IMU state. XML is used for independent transform calculations, not to launch MuJoCo from this directory.

These checks launch no browser and send no servo commands. Browser visuals and the user's physical robot were not accepted by this record. Numerical checks do not establish that physical rollover is solved.
