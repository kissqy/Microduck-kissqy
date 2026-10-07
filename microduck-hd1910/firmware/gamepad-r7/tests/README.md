# GameSir disconnect regression

Run on Linux from the source root. This includes the production C event/error and
reconnect functions, uses real nonblocking pipes and `poll()`, and injects only
hardware discovery, `ioctl`, read failures and the reconnect clock. It does not
open a real input/uinput device or send robot commands.

```bash
cc -std=c11 -O2 -Wall -Wextra -Werror gamepad-r7/tests/test_gamesir_disconnect.c -o /tmp/test-gamesir-disconnect
/tmp/test-gamesir-disconnect
```

Coverage:

- Auxiliary HUP removes and closes only the auxiliary fd; the following poll
  sleeps instead of repeatedly returning HUP, and the main input still forwards
  START, stick, both trigger directions and SYN.
- Main HUP exits into the existing outer reconnect/cleanup path.
- Both sources handle POLLERR/POLLNVAL, EOF, ENODEV, EBADF and EIO as permanent
  failures; EAGAIN/EWOULDBLOCK/EINTR leave the descriptors active.
- Cleanup closes an auxiliary descriptor only once.
- Consumer HOME/media keys stay excluded from the Xbox button map.
- A missing auxiliary node retries at most once per second and is reopened and
  grabbed when it returns. A present auxiliary node causes no discovery scans.

The virtual Xbox identity, axis discovery/scaling and input mappings remain the
same. Auxiliary loss keeps the main virtual controller alive. Full main-device
loss still recreates it through the original outer loop. This test establishes
the error/recovery behavior; it does not claim a measured robot temperature drop.
