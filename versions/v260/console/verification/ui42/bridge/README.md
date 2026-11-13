UI42 GameSir HOME and persistent recording directory evidence

Changed product files:
- native source gamepad-r7/gamesir-xboxd.c, test_mapping.c, tests/test_gamesir_disconnect.c, tests/README.md, and the source-built gamesir-xboxd executable.
- stage gamepad-r7/gamesir-xboxd only; gamesir-xbox-status, service, and udev rule are byte-identical to UI41.
- stage padd.service and gamepad.py: StateDirectory=padd in the base unit and generated override. No last.json migration, deletion or automatic playback.

Native source diff and installer diff are against the UI41 backup/stage. BUILD.json records file hashes, compiler, command and known limits. host-disconnect-tests.log exercises production C paths with real pipes/inotify; there is no hardware claim. host-mapping-tests.log covers the main START/trigger isolation and numeric scaling. installer-state-tests.log runs the real upgrade_client twice under a temporary root with external commands mocked, proving the previous recording is not touched.

Only Consumer KEY_HOMEPAGE and KEY_HOME become BTN_MODE; ambiguous KEY_MENU/media remain isolated. The key descriptor/order and axis discovery/scaling bodies are unchanged, checked byte-for-byte in descriptor-and-axis-invariants.log. Main BTN_MODE and auxiliary HOME use OR-held state; repeats do not add edges. Auxiliary disconnect clears its own level without releasing a Mode still held by the main node. A necessary synthetic release on auxiliary disconnect cannot be distinguished from a physical release through the current virtual Xbox stream; no new source-status protocol was introduced.

The bridge does not start recording or playback itself. It exposes an independent MODE edge to the PADD recorder; long-press interpretation stays outside the bridge. ARM64 ELF checks prove architecture/interpreter compatibility, not physical device behavior.
