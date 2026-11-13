// The numeric readout and its history must use the same fresh telemetry source.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const live = (snapshot, channel) => snapshot.channels?.[channel]?.status === 'live';

export function loopHz(snapshot) {
  // Commissioning publishes bus.achieved_hz. Motion publishes
  // state.loop.hz and health.control_loop.achieved_hz instead.
  const candidates = [
    snapshot.mode === 'service' && live(snapshot, 'bus') ? snapshot.bus?.achieved_hz : null,
    live(snapshot, 'state') ? snapshot.state?.loop?.hz : null,
    live(snapshot, 'health') ? snapshot.health?.control_loop?.achieved_hz : null,
  ];
  return candidates.find(finite) ?? null;
}
