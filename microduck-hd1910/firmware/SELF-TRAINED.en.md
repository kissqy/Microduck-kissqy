[简体中文](SELF-TRAINED.zh-CN.md) | **English** | [Русский](SELF-TRAINED.ru.md)

# R17 v1.0.137 / official 0.15.1 self-trained models

Run / install instructions are in [the console guide](console/USER-GUIDE.en.md) and [bundled firmware guide](packaging/README.en.md). Bundled models: rough-walking teacher 14000 iterations, sit / stand 10000, ground picking 5000, forward roll 10000, and LB recovery teacher 11000. Automatic Stand is empty; LB uses official named skill `stand_test`; stationary holding uses Walk.

This version only replaces the LB model and supports its no-filter contract. Original contracts and weights are preserved byte for byte. Parameter sources and per-model passthrough are described in [settings design](docs/design/r17-settings-design.en.md). Training calibration is retained as provenance; installation continues using the robot's own assembly calibration.
