//! Native Feetech TTL packets. No Dynamixel packets or address translation.
//!
//! HD1910 telemetry uses only the 15-byte feedback block at 56..=70.
//! FT6 shares that 15-byte block length; all 16 devices use one Sync Read.
//! Full IMU age/sequence diagnostics remain at 124 and are not polled per tick.
//! The verified bench surface also includes
//! torque at 40, and the 6-byte position command at 42 (41 is preserved). Model-specific
//! current/gain units are deliberately not guessed from another Feetech model
//! or from XL330.
use std::collections::{BTreeMap, BTreeSet};
use std::f64::consts::TAU;
use std::io::{Read, Write};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};

use crate::imu::SflpDecoder;
use crate::io::{ImuStale, IoError, JointTargets, Result, RobotIo, Sensors, SlowSensors};
use crate::model::{JOINT_NAMES, NUM_JOINTS};

pub const BAUD: u32 = 1_000_000;
pub const IMU_ID: u8 = 200;
pub const SYNC_ADDRESS: u8 = 56;
pub const SYNC_LENGTH: u8 = 15;
pub const SERVO_READ_LENGTH: u8 = 15;
pub const IMU_DIAGNOSTIC_ADDRESS: u8 = 124;
pub const IMU_LENGTH: u8 = 15;
pub const IMU_DIAGNOSTIC_LENGTH: u8 = 20;
pub const IMU_IDENTITY: [u8; 5] = [6, 0, 0, 0, 0xf2];
/// FT6 sets status bit1 at TX when quaternion age exceeds this bound.
pub const IMU_FRESH_BOUND_MS: u16 = 30;
pub const BROADCAST: u8 = 254;
pub const READ: u8 = 2;
pub const WRITE: u8 = 3;
pub const SYNC_READ: u8 = 0x82;
pub const SYNC_WRITE: u8 = 0x83;
/// Budget for one complete 50 Hz telemetry transaction.
/// Setup/torque verification and explicit read-only diagnostics keep their own budget.
pub const TELEMETRY_DEADLINE_MS: u64 = 20;
/// Full telemetry and its host-side age share one 20 ms budget.
/// Retained in diagnostics so consoles can interpret archived timing records.
pub const TELEMETRY_COMPLETE_MAX_AGE_MS: u64 = TELEMETRY_DEADLINE_MS;
pub const READ_TIMING_REVISION: &str = "r15-read-timing.2";
/// Budget for all fifteen torque/goal confirmations at a state transition.
/// Normal telemetry keeps its separate per-tick deadline.
pub const CONTROL_READBACK_DEADLINE_MS: u64 = 10;

fn error(message: impl Into<String>) -> IoError {
    IoError::Bus(message.into())
}

pub fn packet(id: u8, instruction: u8, params: &[u8]) -> Result<Vec<u8>> {
    if id == 255 || params.len() > 253 {
        return Err(error("Feetech invalid ID or packet length"));
    }
    let mut out = vec![255, 255, id, (params.len() + 2) as u8, instruction];
    out.extend_from_slice(params);
    let sum = out[2..].iter().fold(0u8, |a, b| a.wrapping_add(*b));
    out.push(!sum);
    Ok(out)
}

#[derive(Debug, PartialEq)]
pub struct Status {
    pub id: u8,
    pub error: u8,
    pub data: Vec<u8>,
}

/// A bounded stream decoder, including resynchronisation after noise/checksum errors.
#[derive(Default)]
pub struct Decoder {
    bytes: Vec<u8>,
    expected_length: Option<u8>,
    pub bad_checksums: u64,
    pub discarded: u64,
}
impl Decoder {
    pub fn for_sync_read(length: u8) -> Self {
        Self {
            expected_length: length.checked_add(2),
            ..Self::default()
        }
    }
    pub fn push(&mut self, byte: u8) -> Option<Status> {
        self.bytes.push(byte);
        loop {
            if self.bytes.len() < 2 {
                return None;
            }
            if self.bytes[..2] != [255, 255] {
                self.bytes.remove(0);
                self.discarded += 1;
                continue;
            }
            if self.bytes.len() < 4 {
                return None;
            }
            if self.bytes[2] >= BROADCAST
                || self.bytes[3] < 2
                || self
                    .expected_length
                    .is_some_and(|length| self.bytes[3] != length)
            {
                self.bytes.remove(0);
                self.discarded += 1;
                continue;
            }
            let length = usize::from(self.bytes[3]) + 4;
            if self.bytes.len() < length {
                return None;
            }
            let sum = self.bytes[2..length]
                .iter()
                .fold(0u8, |a, b| a.wrapping_add(*b));
            if sum != 255 {
                self.bytes.remove(0);
                self.bad_checksums += 1;
                self.discarded += 1;
                continue;
            }
            let status = Status {
                id: self.bytes[2],
                error: self.bytes[4],
                data: self.bytes[5..length - 1].to_vec(),
            };
            self.bytes.drain(..length);
            return Some(status);
        }
    }
}

fn accept_sync_status(
    pending: &mut BTreeSet<u8>,
    replies: &mut BTreeMap<u8, Vec<u8>>,
    status: Status,
    length: u8,
) -> Result<bool> {
    if !pending.contains(&status.id) {
        return Err(error(format!(
            "unexpected/duplicate Feetech Sync Read reply from ID {}",
            status.id
        )));
    }
    if status.error != 0 {
        return Err(error(format!(
            "Feetech ID {} Sync Read status error 0x{:02x}",
            status.id, status.error
        )));
    }
    if status.data.len() != usize::from(length) {
        return Err(IoError::ShortRead {
            what: "Feetech Sync Read status",
            expected: usize::from(length),
            got: status.data.len(),
        });
    }
    pending.remove(&status.id);
    replies.insert(status.id, status.data);
    Ok(pending.is_empty())
}

pub struct Bus {
    port: Box<dyn serialport::SerialPort>,
    timeout: Duration,
    read_only: bool,
    pub last_sync: SyncTrace,
}

/// Minimal acquisition result. No recovery, raw-packet history or UART polling.
#[derive(Debug, Clone, Default, Serialize)]
pub struct SyncTrace {
    pub address: u8,
    pub length: u8,
    pub missing_ids: Vec<u8>,
    pub bad_checksums: u64,
    pub discarded: u64,
    pub elapsed_us: u64,
    pub rx_bytes: usize,
    pub deadline_exceeded: bool,
    pub complete_but_late: bool,
    /// False if the request could not be sent; do not blame each pending device.
    pub request_sent: bool,
    /// Valid IMU and a strict subset of servo replies; missing IDs stay visible.
    pub partial_received: bool,
}

impl Bus {
    pub fn open(path: &str) -> Result<Self> {
        let builder = serialport::new(path, BAUD).timeout(Duration::from_millis(2));
        #[cfg(unix)]
        let port: Box<dyn serialport::SerialPort> = {
            let mut tty = builder.open_native().map_err(|e| error(e.to_string()))?;
            tty.set_exclusive(true).map_err(|e| error(e.to_string()))?;
            Box::new(tty)
        };
        #[cfg(not(unix))]
        let port = builder.open().map_err(|e| error(e.to_string()))?;
        Ok(Self {
            port,
            timeout: Duration::from_millis(30),
            read_only: false,
            last_sync: SyncTrace::default(),
        })
    }

    /// Enforced at the packet boundary, including every existing write API.
    pub fn open_read_only(path: &str) -> Result<Self> {
        let mut bus = Self::open(path)?;
        bus.read_only = true;
        bus.timeout = Duration::from_millis(40);
        Ok(bus)
    }

    fn send(&mut self, bytes: &[u8], deadline: Instant) -> Result<()> {
        if self.read_only && !matches!(bytes.get(4).copied(), Some(1 | READ | SYNC_READ)) {
            return Err(error("read-only motor bus: write instruction refused"));
        }
        self.port
            .clear(serialport::ClearBuffer::Input)
            .map_err(|e| error(e.to_string()))?;
        let mut remaining = bytes;
        while !remaining.is_empty() {
            self.poll_timeout(deadline)?;
            match self.port.write(remaining) {
                Ok(0) => return Err(error("Feetech request write returned zero")),
                Ok(count) => remaining = &remaining[count..],
                Err(e)
                    if matches!(
                        e.kind(),
                        std::io::ErrorKind::Interrupted
                            | std::io::ErrorKind::TimedOut
                            | std::io::ErrorKind::WouldBlock
                    ) => {}
                Err(e) => return Err(error(e.to_string())),
            }
        }
        // On the HAT, direction is automatic. Start receiving a request's replies
        // immediately: Unix SerialPort::flush calls tcdrain and can delay the
        // control thread after the small request has already left the UART.
        Ok(())
    }

    fn poll_timeout(&mut self, deadline: Instant) -> Result<()> {
        let left = deadline.saturating_duration_since(Instant::now());
        if left.is_zero() {
            return Err(error("Feetech transaction deadline exceeded"));
        }
        self.port
            .set_timeout(left.min(Duration::from_millis(2)))
            .map_err(|e| error(e.to_string()))
    }

    fn exchange(&mut self, id: u8, inst: u8, params: &[u8], count: usize) -> Result<Vec<u8>> {
        self.exchange_budget(id, inst, params, count, self.timeout)
    }

    fn exchange_budget(
        &mut self,
        id: u8,
        inst: u8,
        params: &[u8],
        count: usize,
        budget: Duration,
    ) -> Result<Vec<u8>> {
        if id >= BROADCAST {
            return Err(error("unicast reply required"));
        }
        let tx = packet(id, inst, params)?;
        let deadline = Instant::now() + budget;
        self.send(&tx, deadline)?;
        let mut decoder = Decoder::default();
        let mut one = [0u8; 1];
        while Instant::now() < deadline {
            self.poll_timeout(deadline)?;
            match self.port.read(&mut one) {
                Ok(0) => continue,
                Ok(_) => {
                    if let Some(status) = decoder.push(one[0]) {
                        if status.id != id {
                            continue;
                        }
                        // READ/PING echo is unambiguously an instruction, not an empty
                        // successful status. Do not interpret the echoed READ as error 2.
                        if status.error == inst && status.data == params {
                            continue;
                        }
                        if status.error != 0 {
                            return Err(error(format!(
                                "Feetech ID {id} status error 0x{:02x}",
                                status.error
                            )));
                        }
                        if status.data.len() != count {
                            return Err(IoError::ShortRead {
                                what: "Feetech status",
                                expected: count,
                                got: status.data.len(),
                            });
                        }
                        return Ok(status.data);
                    }
                }
                Err(e)
                    if matches!(
                        e.kind(),
                        std::io::ErrorKind::TimedOut
                            | std::io::ErrorKind::WouldBlock
                            | std::io::ErrorKind::Interrupted
                    ) => {}
                Err(e) => return Err(error(e.to_string())),
            }
        }
        Err(error(format!("Feetech ID {id} response timeout")))
    }

    pub fn ping(&mut self, id: u8) -> Result<()> {
        self.exchange(id, 1, &[], 0).map(|_| ())
    }
    pub fn read(&mut self, id: u8, address: u8, length: u8) -> Result<Vec<u8>> {
        if length == 0 || length > 253 || u16::from(address) + u16::from(length) > 256 {
            return Err(error("invalid Feetech register range"));
        }
        self.exchange(id, READ, &[address, length], usize::from(length))
    }

    /// Unicast write requires an acknowledgement. Never retry a motion write blindly.
    pub fn write(&mut self, id: u8, address: u8, data: &[u8]) -> Result<()> {
        if data.is_empty() || usize::from(address) + data.len() > 256 {
            return Err(error("invalid Feetech write range"));
        }
        let mut params = vec![address];
        params.extend_from_slice(data);
        self.exchange(id, WRITE, &params, 0).map(|_| ())
    }

    /// A broadcast has NO acknowledgement. Success here means sent, not confirmed.
    /// The UART preserves write order; HAT direction is automatic. A following
    /// query confirms transitions without tcdrain sleeping on every position.
    pub fn sync_write(&mut self, address: u8, rows: &[(u8, Vec<u8>)]) -> Result<()> {
        self.send(
            &sync_write_packet(address, rows)?,
            Instant::now() + Duration::from_millis(4),
        )
    }

    /// One bounded transition confirmation, never an automatic retry.
    pub fn read_control(&mut self, id: u8, address: u8, length: u8) -> Result<Vec<u8>> {
        self.exchange_budget(
            id,
            READ,
            &[address, length],
            usize::from(length),
            Duration::from_millis(4),
        )
    }

    /// Exactly one request. A bad or missing reply fails this sample.
    pub fn sync_read(
        &mut self,
        address: u8,
        length: u8,
        ids: &[u8],
    ) -> Result<BTreeMap<u8, Vec<u8>>> {
        self.sync_read_inner(address, length, ids, false)
    }

    fn sync_read_inner(
        &mut self,
        address: u8,
        length: u8,
        ids: &[u8],
        allow_partial: bool,
    ) -> Result<BTreeMap<u8, Vec<u8>>> {
        let started = Instant::now();
        let budget = if address == SYNC_ADDRESS {
            Duration::from_millis(TELEMETRY_DEADLINE_MS)
        } else if ids.len() == NUM_JOINTS && matches!((address, length), (40, 1) | (42, 2)) {
            Duration::from_millis(CONTROL_READBACK_DEADLINE_MS)
        } else {
            Duration::from_millis(4)
        };
        let deadline = started + if self.read_only { self.timeout } else { budget };
        let mut pending = ids.iter().copied().collect::<BTreeSet<_>>();
        let mut decoder = Decoder::for_sync_read(length);
        let mut rx_bytes = 0;
        let mut complete_but_late = false;
        let mut request_sent = false;
        let mut late_bytes = false;
        let result = (|| {
            self.send(&sync_read_packet(address, length, ids)?, deadline)?;
            request_sent = true;
            let mut replies = BTreeMap::new();
            let mut failure = None;
            let mut bytes = [0u8; 256];
            while Instant::now() < deadline {
                if self.poll_timeout(deadline).is_err() {
                    break;
                }
                match self.port.read(&mut bytes) {
                    Ok(count) => {
                        late_bytes |= count > 0 && Instant::now() >= deadline;
                        rx_bytes += count;
                        for byte in &bytes[..count] {
                            if let Some(status) = decoder.push(*byte) {
                                if let Err(error) =
                                    accept_sync_status(&mut pending, &mut replies, status, length)
                                {
                                    failure.get_or_insert(error);
                                }
                            }
                        }
                        if pending.is_empty() {
                            if let Some(error) = failure {
                                return Err(error);
                            }
                            if decoder.bad_checksums > 0 {
                                return Err(error("Feetech Sync Read checksum error"));
                            }
                            let completed = Instant::now();
                            if completed >= deadline {
                                complete_but_late = true;
                                break;
                            }
                            return Ok(replies);
                        }
                    }
                    Err(e)
                        if matches!(
                            e.kind(),
                            std::io::ErrorKind::TimedOut
                                | std::io::ErrorKind::WouldBlock
                                | std::io::ErrorKind::Interrupted
                        ) => {}
                    Err(e) => return Err(error(e.to_string())),
                }
            }
            if let Some(error) = failure {
                return Err(error);
            }
            if complete_but_late {
                return Err(error(
                    "Feetech Sync Read complete but transaction deadline exceeded",
                ));
            }
            // Partial acceptance is telemetry-only. Never soften register/gain/torque
            // confirmation, IMU loss, protocol errors, or a rejected late frame.
            if allow_partial
                && address == SYNC_ADDRESS
                && length == SYNC_LENGTH
                && replies.contains_key(&IMU_ID)
                && !pending.is_empty()
                && !pending.contains(&IMU_ID)
                && decoder.bad_checksums == 0
                && decoder.discarded == 0
                && !late_bytes
            {
                return Ok(replies);
            }
            Err(error(format!(
                "Feetech Sync Read {}; missing IDs {:?}",
                if decoder.bad_checksums > 0 {
                    "checksum error"
                } else {
                    "timeout"
                },
                pending.iter().copied().collect::<Vec<_>>()
            )))
        })();
        let partial_received = result.is_ok() && !pending.is_empty();
        self.last_sync = SyncTrace {
            address,
            length,
            missing_ids: pending.into_iter().collect(),
            bad_checksums: decoder.bad_checksums,
            discarded: decoder.discarded,
            elapsed_us: started.elapsed().as_micros() as u64,
            rx_bytes,
            deadline_exceeded: Instant::now() >= deadline,
            complete_but_late,
            request_sent,
            partial_received,
        };
        result
    }

    /// FT6 and all fifteen joints share the fixed 56/15 block.
    pub fn telemetry(&mut self, servo_ids: &[u8]) -> Result<BTreeMap<u8, Vec<u8>>> {
        if servo_ids.len() != NUM_JOINTS || servo_ids.contains(&IMU_ID) {
            return Err(error("telemetry requires all 15 joints plus IMU 200"));
        }
        let mut ids = [IMU_ID; NUM_JOINTS + 1];
        ids[1..].copy_from_slice(servo_ids);
        self.sync_read(SYNC_ADDRESS, SYNC_LENGTH, &ids)
    }

    fn telemetry_partial(&mut self, servo_ids: &[u8]) -> Result<BTreeMap<u8, Vec<u8>>> {
        if servo_ids.len() != NUM_JOINTS || servo_ids.contains(&IMU_ID) {
            return Err(error("telemetry requires all 15 joints plus IMU 200"));
        }
        let mut ids = vec![IMU_ID];
        ids.extend_from_slice(servo_ids);
        self.sync_read_inner(SYNC_ADDRESS, SYNC_LENGTH, &ids, true)
    }

    pub fn feedback(&mut self, id: u8) -> Result<Feedback> {
        Feedback::decode(&self.read(id, 56, 11)?)
    }

    pub fn imu(&mut self) -> Result<ImuSample> {
        ImuSample::decode_diagnostic(&self.read(
            IMU_ID,
            IMU_DIAGNOSTIC_ADDRESS,
            IMU_DIAGNOSTIC_LENGTH,
        )?)
    }

    pub fn positions(&mut self, rows: &[(u8, u16)]) -> Result<()> {
        let rows = rows
            .iter()
            .map(|(id, p)| Ok((*id, position_command(*p)?.to_vec())))
            .collect::<Result<Vec<_>>>()?;
        self.sync_write(42, &rows)
    }

    /// Motion goals use the servo's signed native coordinate, including its
    /// current turn. Only calibrated joint observations are modulo one turn.
    pub fn signed_positions(&mut self, rows: &[(u8, i32)]) -> Result<()> {
        let rows = rows
            .iter()
            .map(|(id, p)| Ok((*id, signed_position_command(*p)?.to_vec())))
            .collect::<Result<Vec<_>>>()?;
        self.sync_write(42, &rows)
    }

    /// Targeted broadcast, so ID 200 is never included. Read reg 40 afterwards
    /// if the caller needs confirmation (in particular for torque-off).
    pub fn torque(&mut self, ids: &[u8], on: bool) -> Result<()> {
        let rows = ids
            .iter()
            .map(|id| (*id, vec![u8::from(on)]))
            .collect::<Vec<_>>();
        self.sync_write(40, &rows)
    }

    /// One request verifies every requested switch; missing/nonzero replies fail.
    pub fn verify_torque(&mut self, ids: &[u8], on: bool) -> Result<()> {
        let states = self.sync_read(40, 1, ids)?;
        for id in ids {
            if states.get(id).map(Vec::as_slice) != Some(&[u8::from(on)][..]) {
                return Err(error(format!("ID {id} torque state {on} not confirmed")));
            }
        }
        Ok(())
    }
}

pub fn sync_read_packet(address: u8, length: u8, ids: &[u8]) -> Result<Vec<u8>> {
    let mut unique = BTreeSet::new();
    if length == 0
        || length > 253
        || u16::from(address) + u16::from(length) > 256
        || ids.is_empty()
        || ids.len() > 251
        || ids.iter().any(|id| *id >= BROADCAST || !unique.insert(*id))
        || (ids.contains(&IMU_ID) && ids[0] != IMU_ID)
    {
        return Err(error("invalid Feetech Sync Read address/length/ID order"));
    }
    let mut params = Vec::with_capacity(ids.len() + 2);
    params.extend_from_slice(&[address, length]);
    params.extend_from_slice(ids);
    packet(BROADCAST, SYNC_READ, &params)
}

pub fn sync_write_packet(address: u8, rows: &[(u8, Vec<u8>)]) -> Result<Vec<u8>> {
    let Some((_, first)) = rows.first() else {
        return Err(error("empty sync write"));
    };
    let width = first.len();
    let mut ids = BTreeSet::new();
    if width == 0 || usize::from(address) + width > 256 {
        return Err(error("invalid sync write width"));
    }
    let mut params = vec![address, width as u8];
    for (id, data) in rows {
        if *id >= BROADCAST || *id == IMU_ID || !ids.insert(*id) || data.len() != width {
            return Err(error(
                "invalid/duplicate sync write ID or mismatched row length",
            ));
        }
        params.push(*id);
        params.extend_from_slice(data);
    }
    packet(BROADCAST, SYNC_WRITE, &params)
}

/// HD1910 native target: addresses 42..47 only. Register 41 is never written.
pub fn position_command(position: u16) -> Result<[u8; 6]> {
    if position > 4095 {
        return Err(error("HD1910 position outside single-turn range"));
    }
    signed_position_command(i32::from(position))
}

/// HD1910 uses signed magnitude at bit 15 for the position register.
pub fn signed_position_word(position: i32) -> Result<u16> {
    if !(-32767..=32767).contains(&position) {
        return Err(error("HD1910 native position outside signed 15-bit range"));
    }
    Ok(position.unsigned_abs() as u16 | if position < 0 { 0x8000 } else { 0 })
}

fn signed_position_command(position: i32) -> Result<[u8; 6]> {
    let p = signed_position_word(position)?.to_le_bytes();
    Ok([p[0], p[1], 0, 0, 0, 0])
}

fn signed_magnitude(raw: u16, sign_bit: u8) -> i32 {
    let sign = 1u16 << sign_bit;
    let magnitude = i32::from(raw & (sign - 1));
    if raw & sign != 0 {
        -magnitude
    } else {
        magnitude
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Feedback {
    pub position_raw: i32,
    pub position_wire_raw: u16,
    pub position_signed_raw: i32,
    pub speed_raw: i32,
    pub load_raw: i32,
    pub volts: f64,
    pub temperature_c: u8,
    pub register_64_raw: u8,
    pub register_65_raw: u8,
    pub moving: bool,
}
impl Feedback {
    pub fn decode(raw: &[u8]) -> Result<Self> {
        if raw.len() != 11 {
            return Err(IoError::ShortRead {
                what: "HD1910 feedback",
                expected: 11,
                got: raw.len(),
            });
        }
        Ok(Self {
            position_raw: signed_magnitude(u16::from_le_bytes([raw[0], raw[1]]), 15),
            position_wire_raw: u16::from_le_bytes([raw[0], raw[1]]),
            position_signed_raw: signed_magnitude(u16::from_le_bytes([raw[0], raw[1]]), 15),
            speed_raw: signed_magnitude(u16::from_le_bytes([raw[2], raw[3]]), 15),
            load_raw: signed_magnitude(u16::from_le_bytes([raw[4], raw[5]]), 10),
            volts: f64::from(raw[6]) * 0.1,
            temperature_c: raw[7],
            register_64_raw: raw[8],
            register_65_raw: raw[9],
            moving: raw[10] != 0,
        })
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ServoSample {
    pub feedback: Feedback,
    pub current_raw: i32,
}
impl ServoSample {
    pub fn decode(raw: &[u8]) -> Result<Self> {
        if raw.len() != usize::from(SERVO_READ_LENGTH) {
            return Err(IoError::ShortRead {
                what: "HD1910 Sync Read block",
                expected: usize::from(SERVO_READ_LENGTH),
                got: raw.len(),
            });
        }
        Ok(Self {
            feedback: Feedback::decode(&raw[..11])?,
            // Address 69..70 inside the address-56 block.
            current_raw: signed_magnitude(u16::from_le_bytes([raw[13], raw[14]]), 15),
        })
    }
}

/// FT6 fast block: 12 core bytes, u8 sample counter, status, reserved zero.
/// The 20-byte schema at 124 is diagnostic only. Do not fabricate an exact age
/// for the fast block: FT6 status provides a conservative age bound instead.
#[derive(Debug, Clone, PartialEq)]
pub struct ImuSample {
    pub block: [u8; 12],
    pub sequence: u32,
    pub age_ms: Option<u16>,
    pub age_upper_bound_ms: Option<u16>,
    pub status: u8,
    pub ready: bool,
}
impl ImuSample {
    pub fn decode(raw: &[u8]) -> Result<Self> {
        if raw.len() != usize::from(IMU_LENGTH) {
            return Err(IoError::ShortRead {
                what: "Feetech FT6 IMU 56/15",
                expected: usize::from(IMU_LENGTH),
                got: raw.len(),
            });
        }
        if raw[14] != 0 || raw[13] & 0xf0 != 0 {
            return Err(error("unsupported FT6 IMU status/reserved byte"));
        }
        let ready = raw[13] & 0x07 == 0;
        Ok(Self {
            block: raw[..12].try_into().unwrap(),
            sequence: u32::from(raw[12]),
            age_ms: None,
            age_upper_bound_ms: ready.then_some(IMU_FRESH_BOUND_MS),
            status: raw[13],
            ready,
        })
    }

    pub fn decode_diagnostic(raw: &[u8]) -> Result<Self> {
        if raw.len() != usize::from(IMU_DIAGNOSTIC_LENGTH) {
            return Err(error("Feetech IMU diagnostic requires 124/20"));
        }
        if raw[19] != 1 || raw[18] & !1 != 0 {
            return Err(error("unsupported Feetech IMU schema/flags"));
        }
        Ok(Self {
            block: raw[..12].try_into().unwrap(),
            sequence: u32::from_le_bytes(raw[12..16].try_into().unwrap()),
            age_ms: Some(u16::from_le_bytes([raw[16], raw[17]])),
            age_upper_bound_ms: Some(u16::from_le_bytes([raw[16], raw[17]])),
            status: u8::from(raw[18] & 1 == 0),
            ready: raw[18] & 1 != 0,
        })
    }

    pub fn is_fresh(&self, transaction_us: u64) -> bool {
        self.ready
            && self
                .age_upper_bound_ms
                .is_some_and(|age| transaction_us.saturating_add(u64::from(age) * 1000) <= 50_000)
    }
}

/// Installation-specific joint mapping. An unconfirmed mapping is useful for
/// commissioning, but cannot enable motors. No XL330 unit or gain is reused.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Calibration {
    #[serde(default)]
    pub motion_enabled: bool,
    #[serde(default)]
    pub imu_mount_verified: bool,
    /// Sensor-to-trunk rotation [w, x, y, z], not a heading reset.
    #[serde(default = "default_imu_mount")]
    pub imu_mount_quat: [f64; 4],
    pub joints: Vec<JointCalibration>,
    /// Present velocity always uses the pinned HD1910 HD1910 native scale.
    /// This optional calibration is for measured current only.
    #[serde(default)]
    pub current_ma_per_count: f64,
    #[serde(default)]
    pub units_verified: bool,
}
fn default_imu_mount() -> [f64; 4] {
    SflpDecoder::DEFAULT_MOUNT
}
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct JointCalibration {
    pub name: String,
    pub id: u8,
    pub zero_raw: u16,
    pub direction: i8,
    #[serde(default)]
    pub calibrated: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min_rad: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_rad: Option<f64>,
}
impl JointCalibration {
    pub fn position_rad(&self, raw: i32) -> f64 {
        (f64::from(raw) - f64::from(self.zero_raw)) * TAU / 4096.0 * f64::from(self.direction)
    }
    fn raw_position(&self, radians: f64) -> f64 {
        f64::from(self.zero_raw) + radians * f64::from(self.direction) * 4096.0 / TAU
    }
    /// All rows are converted before any packet is sent. Clamp to measured
    /// mechanical limits, never wrap a single-turn joint across its hard stop.
    pub fn target_raw(&self, radians: f64) -> Result<(u16, bool)> {
        if !self.calibrated || !radians.is_finite() {
            return Err(error(format!(
                "{}: target requires a calibrated joint and finite angle",
                self.name
            )));
        }
        let (Some(min), Some(max)) = (self.min_rad, self.max_rad) else {
            return Err(error(format!("{}: joint limits missing", self.name)));
        };
        if !min.is_finite() || !max.is_finite() || min >= max {
            return Err(error(format!("{}: invalid joint limits", self.name)));
        }
        let bounded = radians.clamp(min, max);
        let raw = self.raw_position(bounded).round();
        if !raw.is_finite() || !(0.0..=4095.0).contains(&raw) {
            return Err(error(format!(
                "{}: target outside single-turn encoder range",
                self.name
            )));
        }
        Ok((raw as u16, bounded != radians))
    }
}
impl Calibration {
    fn feedback_speed_scale(&self) -> Option<f64> {
        Some(crate::hd1910::SPEED_RAD_S_PER_COUNT)
    }

    pub fn commissioning(ids: [u8; NUM_JOINTS]) -> Self {
        Self {
            motion_enabled: false,
            imu_mount_verified: false,
            imu_mount_quat: default_imu_mount(),
            joints: JOINT_NAMES
                .iter()
                .zip(ids)
                .map(|(name, id)| JointCalibration {
                    name: (*name).to_owned(),
                    id,
                    zero_raw: 2048,
                    direction: 1,
                    calibrated: false,
                    min_rad: None,
                    max_rad: None,
                })
                .collect(),
            current_ma_per_count: 0.0,
            units_verified: false,
        }
    }
    pub fn validate(&self) -> Result<()> {
        let mount_norm = self.imu_mount_quat.iter().map(|v| v * v).sum::<f64>();
        if !mount_norm.is_finite() || (mount_norm - 1.0).abs() > 1e-6 {
            return Err(error(
                "IMU mounting quaternion must be finite unit length [w,x,y,z]",
            ));
        }
        if self.units_verified
            && (!self.current_ma_per_count.is_finite() || self.current_ma_per_count <= 0.0)
        {
            return Err(error(
                "verified HD1910 current scale must be positive and finite",
            ));
        }
        if self.joints.len() != NUM_JOINTS {
            return Err(error(
                "Feetech configuration requires all 15 joints in official policy order",
            ));
        }
        let mut ids = BTreeSet::new();
        for (i, joint) in self.joints.iter().enumerate() {
            if joint.name != JOINT_NAMES[i]
                || joint.id >= BROADCAST
                || joint.id == IMU_ID
                || !ids.insert(joint.id)
                || joint.zero_raw > 4095
                || ![-1, 1].contains(&joint.direction)
            {
                return Err(error(format!(
                    "invalid Feetech joint mapping at index {i} ({})",
                    JOINT_NAMES[i]
                )));
            }
            match (joint.min_rad, joint.max_rad) {
                (None, None) if !joint.calibrated => {}
                (Some(min), Some(max)) if min.is_finite() && max.is_finite() && min < max => {
                    if [min, max]
                        .iter()
                        .any(|q| !(0.0..=4095.0).contains(&joint.raw_position(*q).round()))
                    {
                        return Err(error(format!(
                            "{}: calibrated limits cross the single-turn encoder boundary",
                            joint.name
                        )));
                    }
                    if !(min..=max).contains(&crate::deployment::home()[i]) {
                        return Err(error(format!(
                            "{}: limits exclude official home angle {}",
                            joint.name,
                            crate::deployment::home()[i]
                        )));
                    }
                }
                _ => {
                    return Err(error(format!(
                        "{}: complete finite min_rad/max_rad required",
                        joint.name
                    )));
                }
            }
        }
        if self.motion_enabled {
            self.validate_motion_fields()?;
        }
        Ok(())
    }
    fn validate_motion_fields(&self) -> Result<()> {
        if !self.imu_mount_verified
            || self.joints.iter().any(|joint| {
                !joint.calibrated || joint.min_rad.is_none() || joint.max_rad.is_none()
            })
        {
            return Err(error(
                "motion requires all 15 calibrated joints, measured limits and verified IMU mounting",
            ));
        }
        Ok(())
    }
    pub fn validate_motion(&self) -> Result<()> {
        self.validate()?;
        if !self.motion_enabled {
            return Err(error(
                "Feetech motion_enabled is false; complete commissioning first",
            ));
        }
        self.validate_motion_fields()
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct FeetechJointDiagnostic {
    pub name: String,
    pub id: u8,
    pub calibrated: bool,
    pub position_raw: i32,
    pub position_wire_raw: u16,
    pub position_signed_raw: i32,
    pub speed_raw: i32,
    pub load_raw: i32,
    pub current_raw: i32,
    pub volts: f64,
    pub temperature_c: u8,
    pub position_rad: Option<f64>,
    pub velocity_rad_s: Option<f64>,
    pub current_ma: Option<f64>,
    pub feedback_fresh: bool,
    pub sample_age_ms: u64,
    pub missing_total: u64,
    pub consecutive_missing: u32,
    pub read_recovery: &'static str,
}
/// Cumulative telemetry evidence, retained independently of browser polling and
/// torque/goal confirmation reads. A missing reply means no valid status frame.
#[derive(Debug, Clone, Default, Serialize)]
pub struct TelemetryTotals {
    pub session: String,
    pub total_reads: u64,
    pub failed_reads: u64,
    pub complete_but_late: u64,
    pub accepted_complete_but_late: u64,
    pub last_complete_but_late: Option<TelemetryLateRead>,
    pub missing_by_id: BTreeMap<u8, u64>,
    pub last_missing_read_by_id: BTreeMap<u8, u64>,
    pub last_error: Option<String>,
    pub last_failure: Option<TelemetryFailure>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TelemetryFailure {
    pub read: u64,
    pub error: String,
    pub missing_ids: Vec<u8>,
    pub elapsed_us: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct TelemetryLateRead {
    pub read: u64,
    pub elapsed_us: u64,
    /// Accepted by the transport; the normal IMU freshness checks still follow.
    pub accepted: bool,
}

impl TelemetryTotals {
    fn new() -> Self {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        Self {
            session: format!("{}-{stamp}", std::process::id()),
            ..Self::default()
        }
    }

    fn observe(&mut self, trace: &SyncTrace, failure: Option<String>) {
        // This is called once at the acquisition site, never by a status query.
        if trace.address != SYNC_ADDRESS || trace.length != SYNC_LENGTH {
            return;
        }
        // An accepted partial sample is still an incomplete bus acquisition.
        // Count its missing replies without turning it into a control-loop error.
        let failure = failure.or_else(|| {
            (trace.request_sent && trace.partial_received && !trace.missing_ids.is_empty()).then(
                || {
                    format!(
                        "Feetech telemetry partial; missing IDs {:?}; per-joint recovery active",
                        trace.missing_ids
                    )
                },
            )
        });
        self.total_reads = self.total_reads.saturating_add(1);
        self.last_error = failure.clone();
        if trace.complete_but_late {
            self.complete_but_late = self.complete_but_late.saturating_add(1);
            let accepted = failure.is_none();
            if accepted {
                self.accepted_complete_but_late = self.accepted_complete_but_late.saturating_add(1);
            }
            self.last_complete_but_late = Some(TelemetryLateRead {
                read: self.total_reads,
                elapsed_us: trace.elapsed_us,
                accepted,
            });
        }
        if let Some(error) = failure {
            self.failed_reads = self.failed_reads.saturating_add(1);
            let missing_ids = if trace.request_sent {
                trace
                    .missing_ids
                    .iter()
                    .copied()
                    .collect::<BTreeSet<_>>()
                    .into_iter()
                    .collect::<Vec<_>>()
            } else {
                Vec::new()
            };
            for id in &missing_ids {
                let count = self.missing_by_id.entry(*id).or_default();
                *count = count.saturating_add(1);
                self.last_missing_read_by_id.insert(*id, self.total_reads);
            }
            self.last_failure = Some(TelemetryFailure {
                read: self.total_reads,
                error,
                missing_ids,
                elapsed_us: trace.elapsed_us,
            });
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct FeetechDiagnostics {
    pub backend: &'static str,
    pub read_timing_revision: &'static str,
    pub motion_enabled: bool,
    pub calibration_complete: bool,
    pub imu_mount_verified: bool,
    /// True only after this process explicitly enabled every configured motor.
    pub torque_enabled: bool,
    /// None at startup or after an unconfirmed transaction; not a claim of limp.
    pub torque_state_confirmed: Option<bool>,
    pub gain_mode: &'static str,
    pub velocity_source: &'static str,
    /// Unfiltered native speed scale, before the installed joint direction.
    /// None for the generic position-derivative fallback.
    pub velocity_rad_s_per_count: Option<f64>,
    pub current_available: bool,
    pub sample_age_ms: Option<u64>,
    pub imu_ready: bool,
    pub imu_sequence: Option<u32>,
    pub imu_age_ms: Option<u16>,
    pub imu_age_upper_bound_ms: Option<u16>,
    pub imu_status: Option<u8>,
    pub command_clamps_total: u64,
    pub partial_samples_total: u64,
    pub all_joints_fresh: bool,
    pub stale_joint_ids: Vec<u8>,
    pub held_joint_ids: Vec<u8>,
    pub joints: Vec<FeetechJointDiagnostic>,
    pub sync: SyncTrace,
    pub telemetry: TelemetryTotals,
    pub hd1910: crate::hd1910::Diagnostics,
}

/// The HOME start guard needs these flags before targets are applied, while the
/// published diagnostics must include the writes later in the same tick.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FeetechControlStatus {
    pub all_joints_fresh: bool,
    pub imu_mount_verified: bool,
    pub imu_ready: bool,
    pub torque_state_confirmed: Option<bool>,
    pub joints_held: bool,
}

impl From<&FeetechDiagnostics> for FeetechControlStatus {
    fn from(diagnostics: &FeetechDiagnostics) -> Self {
        Self {
            all_joints_fresh: diagnostics.all_joints_fresh,
            imu_mount_verified: diagnostics.imu_mount_verified,
            imu_ready: diagnostics.imu_ready,
            torque_state_confirmed: diagnostics.torque_state_confirmed,
            joints_held: !diagnostics.held_joint_ids.is_empty(),
        }
    }
}

// Same nominal allowance as robotd's official Coast: three missed ticks.
// A wall-clock cap also bounds a delayed loop (20 ms * 3 + one read budget).
const JOINT_COAST_TICKS: u32 = 3;
const JOINT_COAST_MAX_AGE: Duration = Duration::from_millis(80);

#[derive(Clone)]
struct JointFeedback {
    at: Instant,
    sample: ServoSample,
    position: f64,
    // Last published (possibly filtered) velocity, retained during the coast.
    velocity: f64,
}

/// Official RobotIo with native FT6 reads and HD1910 position writes. Startup
/// is read-only; an explicit bring-up enables motion.
pub struct FeetechIo {
    pub bus: Bus,
    calibration: Calibration,
    decoder: SflpDecoder,
    last_sequence: Option<u32>,
    stale: ImuStale,
    latest_ready: bool,
    latest_slow: Option<SlowSensors>,
    latest_sample_at: Option<Instant>,
    joint_feedback: [Option<JointFeedback>; NUM_JOINTS],
    joint_missing: [u32; NUM_JOINTS],
    joint_missing_total: [u64; NUM_JOINTS],
    partial_samples_total: u64,
    latest_partial: bool,
    latest_native_positions: Option<[i32; NUM_JOINTS]>,
    latest_joints: Vec<FeetechJointDiagnostic>,
    latest_imu_age_ms: Option<u16>,
    latest_imu_age_upper_bound_ms: Option<u16>,
    latest_imu_status: Option<u8>,
    torque_enabled: bool,
    command_enabled: bool,
    torque_state_confirmed: Option<bool>,
    command_clamps_total: u64,
    gain_notice_logged: bool,
    telemetry: TelemetryTotals,
    telemetry_sync: SyncTrace,
    hd1910: crate::hd1910::State,
    snapshot_metadata: std::sync::OnceLock<std::sync::Arc<crate::feetech_snapshot::Metadata>>,
}
impl FeetechIo {
    pub fn open(path: &str, calibration: Calibration) -> Result<Self> {
        calibration.validate()?;
        Self::from_bus(Bus::open(path)?, calibration)
    }
    pub fn from_bus(mut bus: Bus, calibration: Calibration) -> Result<Self> {
        calibration.validate()?;
        if bus.read(IMU_ID, 0, 5)? != IMU_IDENTITY {
            return Err(error(
                "ID 200 requires FT6 firmware (06 00 00 00 f2); flash FT6 before enabling IMU",
            ));
        }
        let decoder = SflpDecoder::new(calibration.imu_mount_quat);
        let mut io = Self {
            bus,
            calibration,
            decoder,
            last_sequence: None,
            stale: ImuStale::default(),
            latest_ready: false,
            latest_slow: None,
            latest_sample_at: None,
            joint_feedback: std::array::from_fn(|_| None),
            joint_missing: [0; NUM_JOINTS],
            joint_missing_total: [0; NUM_JOINTS],
            partial_samples_total: 0,
            latest_partial: false,
            latest_native_positions: None,
            latest_joints: Vec::new(),
            latest_imu_age_ms: None,
            latest_imu_age_upper_bound_ms: None,
            latest_imu_status: None,
            torque_enabled: false,
            command_enabled: false,
            torque_state_confirmed: None,
            command_clamps_total: 0,
            gain_notice_logged: false,
            telemetry: TelemetryTotals::new(),
            telemetry_sync: SyncTrace::default(),
            hd1910: crate::hd1910::State::default(),
            snapshot_metadata: std::sync::OnceLock::new(),
        };
        // Opening a device is read-only, as on the upstream Dynamixel backend.
        // A daemon restart must not drop a standing robot. Report actual torque;
        // only an explicit init/enable may begin position writes in this process.
        let states = io.bus.sync_read(40, 1, &io.ids())?;
        let all_on = states.values().all(|v| v == &[1]);
        let all_off = states.values().all(|v| v == &[0]);
        io.torque_enabled = all_on;
        io.torque_state_confirmed = if all_on {
            Some(true)
        } else if all_off {
            Some(false)
        } else {
            None
        };
        {
            io.hd1910.inspect(&mut io.bus, &io.calibration)?;
        }
        Ok(io)
    }
    fn ids(&self) -> Vec<u8> {
        self.calibration
            .joints
            .iter()
            .map(|joint| joint.id)
            .collect()
    }
    fn require_fresh_sample(&self) -> Result<()> {
        if self
            .latest_sample_at
            .is_none_or(|time| time.elapsed() > Duration::from_millis(100))
            || self.latest_partial
            || self.joint_missing.iter().any(|n| *n != 0)
        {
            return Err(error(
                "Feetech motion requires a complete sample no older than 100 ms",
            ));
        }
        Ok(())
    }
}
impl FeetechIo {
    /// Optional temporary test settings, kept outside the official pad config.
    pub fn configure_servo_test(&mut self, calibration_path: &std::path::Path) -> Result<()> {
        self.hd1910.test_parameters = crate::hd1910_test::load(calibration_path)?;
        Ok(())
    }
    fn joint_holding(&self, i: usize, now: Instant) -> bool {
        self.joint_feedback[i].as_ref().is_some_and(|previous| {
            self.joint_missing[i] > JOINT_COAST_TICKS
                || now.saturating_duration_since(previous.at) > JOINT_COAST_MAX_AGE
        })
    }

    fn read_sample(&mut self, allow_partial: bool) -> Result<Sensors> {
        let started = Instant::now();
        let result = if allow_partial {
            self.bus.telemetry_partial(&self.ids())
        } else {
            self.bus.telemetry(&self.ids())
        };
        self.telemetry_sync = self.bus.last_sync.clone();
        self.telemetry.observe(
            &self.telemetry_sync,
            result.as_ref().err().map(ToString::to_string),
        );
        // Recovery still tracks unavailable samples. A request that was never
        // sent must not increase per-device physical missing-response totals.
        for (i, joint) in self.calibration.joints.iter().enumerate() {
            if self.bus.last_sync.missing_ids.contains(&joint.id) {
                self.joint_missing[i] = self.joint_missing[i].saturating_add(1);
                if self.telemetry_sync.request_sent {
                    self.joint_missing_total[i] = self.joint_missing_total[i].saturating_add(1);
                }
            }
        }
        let mut blocks = result?;
        let raw_imu = ImuSample::decode(
            &blocks
                .remove(&IMU_ID)
                .ok_or_else(|| error("Feetech Sync Read omitted IMU ID 200"))?,
        )?;
        if self.last_sequence == Some(raw_imu.sequence) {
            self.stale.total = self.stale.total.saturating_add(1);
            self.stale.run = self.stale.run.saturating_add(1);
        } else {
            self.stale.run = 0;
        }
        self.last_sequence = Some(raw_imu.sequence);
        if !raw_imu.is_fresh(self.bus.last_sync.elapsed_us) || self.stale.run >= 3 {
            return Err(error(
                "Feetech IMU not ready or stale (>50 ms / 3 repeated reads)",
            ));
        }
        let mut out = Sensors {
            imu: self.decoder.decode(&raw_imu.block),
            ..Sensors::default()
        };
        let mut fresh = [false; NUM_JOINTS];
        let mut samples = Vec::with_capacity(NUM_JOINTS);
        let mut joints = Vec::with_capacity(NUM_JOINTS);
        let mut volts = 0.0;
        let mut temps = [0.0; NUM_JOINTS];
        let mut raws = [0; NUM_JOINTS];
        for (i, joint) in self.calibration.joints.iter().enumerate() {
            let sample = match blocks.remove(&joint.id) {
                Some(raw) => {
                    fresh[i] = true;
                    ServoSample::decode(&raw).map_err(|e| error(format!("ID {} {e}", joint.id)))?
                }
                None => self.joint_feedback[i]
                    .as_ref()
                    .ok_or_else(|| {
                        error(format!(
                            "ID {} missing without a previous valid sample",
                            joint.id
                        ))
                    })?
                    .sample
                    .clone(),
            };
            let fb = &sample.feedback;
            raws[i] = fb.position_signed_raw;
            out.positions[i] = if joint.calibrated {
                joint.position_rad(fb.position_raw)
            } else {
                f64::NAN
            };
            out.velocities[i] = if !fresh[i] {
                let previous = self.joint_feedback[i].as_ref().unwrap();
                if self.joint_holding(i, started) {
                    0.0
                } else {
                    previous.velocity
                }
            } else if !joint.calibrated {
                f64::NAN
            } else {
                f64::from(fb.speed_raw)
                    * crate::hd1910::SPEED_RAD_S_PER_COUNT
                    * f64::from(joint.direction)
            };
            out.currents_ma[i] = if self.calibration.units_verified {
                f64::from(sample.current_raw.abs()) * self.calibration.current_ma_per_count
            } else {
                f64::NAN
            };
            volts += fb.volts;
            temps[i] = f64::from(fb.temperature_c);
            joints.push(FeetechJointDiagnostic {
                name: joint.name.clone(),
                id: joint.id,
                calibrated: joint.calibrated,
                position_raw: fb.position_raw,
                position_wire_raw: fb.position_wire_raw,
                position_signed_raw: fb.position_signed_raw,
                speed_raw: fb.speed_raw,
                load_raw: fb.load_raw,
                current_raw: sample.current_raw,
                volts: fb.volts,
                temperature_c: fb.temperature_c,
                position_rad: out.positions[i].is_finite().then_some(out.positions[i]),
                velocity_rad_s: None,
                current_ma: out.currents_ma[i].is_finite().then_some(out.currents_ma[i]),
                feedback_fresh: fresh[i],
                sample_age_ms: 0,
                missing_total: self.joint_missing_total[i],
                consecutive_missing: if fresh[i] { 0 } else { self.joint_missing[i] },
                read_recovery: if fresh[i] {
                    "fresh"
                } else if self.joint_holding(i, started) {
                    "holding"
                } else {
                    "coasting"
                },
            });
            samples.push(sample);
        }
        if !blocks.is_empty() {
            return Err(error("unexpected Feetech Sync Read reply IDs"));
        }
        if !raw_imu.is_fresh(started.elapsed().as_micros() as u64) {
            return Err(error(
                "Feetech telemetry cycle too slow; IMU sample now older than 50 ms",
            ));
        }
        self.hd1910.delay_velocity(started, &mut out, &fresh);
        // Commit together only after the current IMU and every used servo value validate.
        for (i, sample) in samples.into_iter().enumerate() {
            joints[i].velocity_rad_s = out.velocities[i].is_finite().then_some(out.velocities[i]);
            if fresh[i] {
                self.joint_feedback[i] = Some(JointFeedback {
                    at: started,
                    sample,
                    position: out.positions[i],
                    velocity: out.velocities[i],
                });
                self.joint_missing[i] = 0;
            }
        }
        self.latest_partial = fresh.iter().any(|v| !v);
        if self.latest_partial {
            self.partial_samples_total = self.partial_samples_total.saturating_add(1);
        }
        self.latest_sample_at = Some(started); // current IMU/control sample, not every joint
        self.latest_native_positions = Some(raws);
        self.latest_joints = joints;
        self.latest_imu_age_ms = raw_imu.age_ms;
        self.latest_imu_age_upper_bound_ms = raw_imu.age_upper_bound_ms;
        self.latest_imu_status = Some(raw_imu.status);
        self.latest_slow = Some(SlowSensors {
            volts: volts / NUM_JOINTS as f64,
            temps_c: temps,
        });
        self.latest_ready = true;
        Ok(out)
    }
}
impl RobotIo for FeetechIo {
    fn reboot(&mut self, _id: u8) -> crate::io::Result<()> {
        Err(crate::io::IoError::Bus(
            "HD1910 reboot is not supported by this native backend".into(),
        ))
    }
    fn measures_load(&self) -> bool {
        false
    }
    fn read(&mut self) -> Result<Sensors> {
        self.read_sample(true)
    }

    fn held_joint_positions(&self) -> [Option<f64>; NUM_JOINTS] {
        let now = Instant::now();
        std::array::from_fn(|i| {
            self.joint_feedback[i]
                .as_ref()
                .filter(|_| self.joint_holding(i, now))
                .map(|old| old.position)
        })
    }
    fn write(&mut self, targets: &JointTargets) -> Result<()> {
        // Calibration is immutable here, validated at open and again before
        // torque-on. Per-target conversion below still checks angles and limits.
        // The official loop publishes targets even before bring-up. Do not leave
        // latent motion targets in an unpowered servo, or touch a restarted robot.
        if !self.command_enabled {
            return Ok(());
        }
        // The official control loop owns sample age: briefly coast on the last
        // observation, then command the last measured pose until reads recover.
        // Rejecting that hold because of its age would turn a read loss into a
        // write failure and release torque. Torque-on still requires fresh data.
        if self.latest_sample_at.is_none() {
            return Err(error("Feetech target write requires a completed sample"));
        }
        if targets.positions.iter().any(|v| !v.is_finite()) {
            return Err(error("Feetech target must be finite"));
        }
        let held = self.held_joint_positions();
        let mut clamps = 0;
        let rows = self
            .calibration
            .joints
            .iter()
            .zip(targets.positions)
            .enumerate()
            .map(|(i, (joint, radians))| {
                let (raw, clamped) = joint.target_raw(held[i].unwrap_or(radians))?;
                if clamped {
                    clamps += 1;
                }
                Ok((joint.id, i32::from(raw)))
            })
            .collect::<Result<Vec<_>>>()?;
        self.bus.signed_positions(&rows)?;
        self.command_clamps_total = self.command_clamps_total.saturating_add(clamps);
        Ok(())
    }
    fn set_gain(&mut self, _kp: u16) -> Result<()> {
        // XL330 gains are not a portable unit. Retain the configured HD1910
        // controller gains; explicit relax uses the native torque register.
        if !self.gain_notice_logged {
            tracing::warn!(
                "Feetech retains native servo gains; XL330 gain requests are not written"
            );
            self.gain_notice_logged = true;
        }
        Ok(())
    }
    fn set_torque(&mut self, on: bool) -> Result<()> {
        let ids = self.ids();
        let previously_off = self.torque_state_confirmed == Some(false);
        if on {
            self.calibration.validate_motion()?;
            self.require_fresh_sample()?;
            if !self.imu_ready() {
                return Err(error("Feetech torque-on requires a fresh converged IMU"));
            }
            {
                self.hd1910.arm(&mut self.bus, &self.calibration)?;
                // Register inspection can take several transactions. Preload a NEW
                // measured position after it, never the sample from before setup.
                self.read_sample(false)?;
                self.require_fresh_sample()?;
            }
            let raw = self
                .latest_native_positions
                .ok_or_else(|| error("Feetech torque-on needs measured positions"))?;
            let rows = ids.iter().copied().zip(raw).collect::<Vec<_>>();
            // Replace any old stored goal BEFORE torque enable, then the official
            // home ramp starts from the same freshly measured pose.
            self.bus.signed_positions(&rows)?;
            let goals = self.bus.sync_read(42, 2, &ids)?;
            for (id, position) in rows {
                if goals[&id] != signed_position_word(position)?.to_le_bytes() {
                    return Err(error(format!(
                        "ID {id}: preloaded hold target not confirmed; torque not enabled"
                    )));
                }
            }
        }
        self.command_enabled = false;
        self.torque_state_confirmed = None;
        let verify = self
            .bus
            .torque(&ids, on)
            .and_then(|()| self.bus.verify_torque(&ids, on))
            .and_then(|()| {
                // The one-shot goal/torque readbacks can outlast a control tick.
                // Refresh from the real FT5 transaction before allowing its first
                // position command; never stretch the sample-age requirement.
                if on {
                    self.read_sample(false).map(|_| ())
                } else {
                    Ok(())
                }
            });
        if let Err(problem) = verify {
            // Roll back only a newly requested OFF -> ON transition. Do not drop
            // already powered motors because a confirmation reply was lost.
            if on && previously_off {
                if let Err(stop) = self.bus.torque(&ids, false) {
                    return Err(error(format!(
                        "{problem}; rollback torque-off also failed: {stop}"
                    )));
                }
                let stopped = self.bus.verify_torque(&ids, false);
                match stopped {
                    Ok(()) => self.torque_state_confirmed = Some(false),
                    Err(stop) => return Err(error(format!("{problem}; {stop}"))),
                }
            }
            return Err(problem);
        }
        self.torque_enabled = on;
        self.command_enabled = on;
        self.torque_state_confirmed = Some(on);
        if !on {
            self.hd1910.disarm(&mut self.bus)?;
        }
        Ok(())
    }
    fn slow_sensors(&mut self) -> Result<SlowSensors> {
        self.latest_slow
            .ok_or_else(|| error("no completed Feetech Sync Read sample yet"))
    }
    fn imu_stale(&self) -> ImuStale {
        self.stale
    }
    fn imu_ready(&self) -> bool {
        self.latest_ready && self.decoder.ready()
    }
    fn feetech_control_status(&self) -> Option<FeetechControlStatus> {
        let now = Instant::now();
        Some(FeetechControlStatus {
            all_joints_fresh: !self.latest_joints.is_empty()
                && (0..self.latest_joints.len()).all(|i| {
                    self.joint_missing[i] == 0
                        && self.joint_feedback[i]
                            .as_ref()
                            .is_some_and(|old| Some(old.at) == self.latest_sample_at)
                }),
            imu_mount_verified: self.calibration.imu_mount_verified,
            imu_ready: self.imu_ready(),
            torque_state_confirmed: self.torque_state_confirmed,
            joints_held: (0..self.latest_joints.len()).any(|i| self.joint_holding(i, now)),
        })
    }
    fn feetech_diagnostics(&self) -> Option<FeetechDiagnostics> {
        let now = Instant::now();
        let mut joints = self.latest_joints.clone();
        let mut stale_joint_ids = Vec::new();
        let mut held_joint_ids = Vec::new();
        for (i, diagnostic) in joints.iter_mut().enumerate() {
            let old = self.joint_feedback[i].as_ref().unwrap();
            diagnostic.sample_age_ms = now.saturating_duration_since(old.at).as_millis() as u64;
            diagnostic.missing_total = self.joint_missing_total[i];
            diagnostic.consecutive_missing = self.joint_missing[i];
            diagnostic.feedback_fresh =
                self.joint_missing[i] == 0 && Some(old.at) == self.latest_sample_at;
            if !diagnostic.feedback_fresh {
                stale_joint_ids.push(diagnostic.id);
            }
            if self.joint_holding(i, now) {
                diagnostic.read_recovery = "holding";
                held_joint_ids.push(diagnostic.id);
            } else if !diagnostic.feedback_fresh {
                diagnostic.read_recovery = "coasting";
            }
        }
        Some(FeetechDiagnostics {
            backend: "feetech_ft6",
            read_timing_revision: READ_TIMING_REVISION,
            motion_enabled: self.calibration.motion_enabled,
            calibration_complete: self.calibration.joints.iter().all(|j| j.calibrated),
            imu_mount_verified: self.calibration.imu_mount_verified,
            torque_enabled: self.torque_enabled,
            torque_state_confirmed: self.torque_state_confirmed,
            gain_mode: if self.hd1910.test_parameters.is_some() {
                "hd1910_console_servo_test_restore_on_relax"
            } else {
                "hd1910_bam_p_d20_mouth_p10_restore_on_relax"
            },
            velocity_source: crate::hd1910::VELOCITY_SOURCE,
            velocity_rad_s_per_count: self.calibration.feedback_speed_scale(),
            current_available: self.calibration.units_verified,
            sample_age_ms: self
                .latest_sample_at
                .map(|time| time.elapsed().as_millis() as u64),
            imu_ready: self.imu_ready(),
            imu_sequence: self.last_sequence,
            imu_age_ms: self.latest_imu_age_ms,
            imu_age_upper_bound_ms: self.latest_imu_age_upper_bound_ms,
            imu_status: self.latest_imu_status,
            command_clamps_total: self.command_clamps_total,
            partial_samples_total: self.partial_samples_total,
            all_joints_fresh: stale_joint_ids.is_empty() && !joints.is_empty(),
            stale_joint_ids,
            held_joint_ids,
            joints,
            sync: self.telemetry_sync.clone(),
            telemetry: self.telemetry.clone(),
            hd1910: self.hd1910.diagnostics(),
        })
    }

    fn feetech_sync_trace(&self) -> Option<&SyncTrace> {
        Some(&self.telemetry_sync)
    }

    fn feetech_snapshot(&self) -> Option<crate::feetech_snapshot::Snapshot> {
        use crate::feetech_snapshot as snapshot;
        let metadata = self
            .snapshot_metadata
            .get_or_init(|| {
                std::sync::Arc::new(snapshot::Metadata {
                    backend: "feetech_ft6",
                    read_timing_revision: READ_TIMING_REVISION,
                    motion_enabled: self.calibration.motion_enabled,
                    calibration_complete: self.calibration.joints.iter().all(|j| j.calibrated),
                    imu_mount_verified: self.calibration.imu_mount_verified,
                    velocity_source: crate::hd1910::VELOCITY_SOURCE,
                    velocity_rad_s_per_count: self.calibration.feedback_speed_scale(),
                    current_available: self.calibration.units_verified,
                    joints: self
                        .calibration
                        .joints
                        .iter()
                        .map(|j| snapshot::JointMetadata {
                            name: j.name.clone(),
                            id: j.id,
                            calibrated: j.calibrated,
                        })
                        .collect(),
                })
            })
            .clone();
        let now = Instant::now();
        let mut joints = snapshot::Samples::default();
        let mut stale_joint_ids = snapshot::Samples::default();
        let mut held_joint_ids = snapshot::Samples::default();
        for (i, original) in self.latest_joints.iter().enumerate() {
            let previous = self.joint_feedback[i].as_ref().unwrap();
            let fresh = self.joint_missing[i] == 0 && Some(previous.at) == self.latest_sample_at;
            let held = self.joint_holding(i, now);
            if !fresh {
                stale_joint_ids.values[stale_joint_ids.len] = original.id;
                stale_joint_ids.len += 1;
            }
            if held {
                held_joint_ids.values[held_joint_ids.len] = original.id;
                held_joint_ids.len += 1;
            }
            joints.values[i] = snapshot::Joint {
                id: original.id,
                position_raw: original.position_raw,
                position_wire_raw: original.position_wire_raw,
                position_signed_raw: original.position_signed_raw,
                speed_raw: original.speed_raw,
                load_raw: original.load_raw,
                current_raw: original.current_raw,
                volts: original.volts,
                temperature_c: original.temperature_c,
                position_rad: original.position_rad,
                velocity_rad_s: original.velocity_rad_s,
                current_ma: original.current_ma,
                feedback_fresh: fresh,
                sample_age_ms: now.saturating_duration_since(previous.at).as_millis() as u64,
                missing_total: self.joint_missing_total[i],
                consecutive_missing: self.joint_missing[i],
                read_recovery: if held {
                    "holding"
                } else if !fresh {
                    "coasting"
                } else {
                    "fresh"
                },
            };
            joints.len += 1;
        }
        let hd1910 = self.hd1910.diagnostics();
        Some(snapshot::Snapshot {
            metadata: metadata.clone(),
            dynamic: snapshot::Dynamic {
                torque_enabled: self.torque_enabled,
                torque_state_confirmed: self.torque_state_confirmed,
                gain_mode: if self.hd1910.test_parameters.is_some() {
                    "hd1910_console_servo_test_restore_on_relax"
                } else {
                    "hd1910_bam_p_d20_mouth_p10_restore_on_relax"
                },
                sample_age_ms: self
                    .latest_sample_at
                    .map(|at| now.saturating_duration_since(at).as_millis() as u64),
                imu_ready: self.imu_ready(),
                imu_sequence: self.last_sequence,
                imu_age_ms: self.latest_imu_age_ms,
                imu_age_upper_bound_ms: self.latest_imu_age_upper_bound_ms,
                imu_status: self.latest_imu_status,
                command_clamps_total: self.command_clamps_total,
                partial_samples_total: self.partial_samples_total,
                all_joints_fresh: stale_joint_ids.len == 0 && joints.len != 0,
                stale_joint_ids,
                held_joint_ids,
                joints: snapshot::JointSamples {
                    samples: joints,
                    metadata,
                },
                sync: self.telemetry_sync.clone(),
                telemetry: self.telemetry.clone(),
                hd1910: snapshot::HdState {
                    temporary_gains_applied: hd1910.temporary_gains_applied,
                    restore_pending: hd1910.restore_pending,
                },
            },
            hd1910,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn position_feedback_and_angles_keep_the_unmodified_signed_coordinate() {
        for (wire, expected) in [
            (0u16, 0),
            (1412, 1412),
            (4095, 4095),
            (32768, 0),
            (34180, -1412),
            (36863, -4095),
            (4096, 4096),
            (5000, 5000),
            (0x9000, -4096),
            (0x7fff, 32767),
            (0xffff, -32767),
            (0x8001, -1),
        ] {
            let mut raw = [0u8; 15];
            raw[..2].copy_from_slice(&wire.to_le_bytes());
            let sample = ServoSample::decode(&raw).unwrap();
            assert_eq!(sample.feedback.position_raw, expected);
            assert_eq!(sample.feedback.position_wire_raw, wire);
            assert_eq!(sample.feedback.position_signed_raw, expected);
        }
        let c = calibrated();
        for id in [12, 22] {
            let joint = c.joints.iter().find(|j| j.id == id).unwrap();
            for position in [-32767, -4095, -1412, -1, 4096, 32767] {
                let expected = (f64::from(position) - f64::from(joint.zero_raw)) * TAU / 4096.0
                    * f64::from(joint.direction);
                assert_eq!(joint.position_rad(position), expected);
            }
        }
    }

    #[test]
    fn native_goal_encoding_is_signed_magnitude_not_twos_complement_or_modulo() {
        for position in [
            -32767, -6048, -4096, -1820, -1323, -1, 0, 2773, 4096, 6244, 32767,
        ] {
            let command = signed_position_command(position).unwrap();
            let wire = u16::from_le_bytes([command[0], command[1]]);
            assert_eq!(signed_magnitude(wire, 15), position);
            assert_eq!(command[2..], [0, 0, 0, 0]);
        }
        assert_eq!(signed_position_word(-1323).unwrap(), 34091);
        for position in [-32768, 32768, i32::MIN, i32::MAX] {
            assert!(signed_position_command(position).is_err());
        }
        // The separate commissioning single-turn API keeps its existing range.
        assert!(position_command(4096).is_err());
    }

    #[test]
    fn telemetry_totals_preserve_every_missing_reply_through_recovery() {
        let mut totals = TelemetryTotals::new();
        let mut trace = SyncTrace {
            address: 56,
            length: 15,
            request_sent: true,
            missing_ids: vec![14, 32],
            ..SyncTrace::default()
        };
        totals.observe(&trace, Some("missing 14,32".into()));
        trace.missing_ids = vec![32];
        totals.observe(&trace, Some("missing 32".into()));
        trace.missing_ids.clear();
        totals.observe(&trace, None);
        assert_eq!((totals.total_reads, totals.failed_reads), (3, 2));
        assert_eq!(totals.missing_by_id, BTreeMap::from([(14, 1), (32, 2)]));
        assert_eq!(
            totals.last_missing_read_by_id,
            BTreeMap::from([(14, 1), (32, 2)])
        );
        assert!(totals.last_error.is_none());
        assert_eq!(totals.last_failure.as_ref().unwrap().read, 2);
        assert_eq!(totals.last_failure.as_ref().unwrap().missing_ids, [32]);
        assert!(!totals.session.is_empty());
        assert_ne!(totals.session, TelemetryTotals::new().session);
    }

    #[test]
    fn telemetry_totals_do_not_blame_devices_for_late_or_unsent_requests() {
        let mut totals = TelemetryTotals::new();
        let mut trace = SyncTrace {
            address: 56,
            length: 15,
            request_sent: true,
            complete_but_late: true,
            ..SyncTrace::default()
        };
        totals.observe(
            &trace,
            Some("complete but transaction deadline exceeded".into()),
        );
        trace.request_sent = false;
        trace.complete_but_late = false;
        trace.missing_ids = telemetry_ids();
        totals.observe(&trace, Some("serial send failed".into()));
        assert_eq!(
            (
                totals.total_reads,
                totals.failed_reads,
                totals.complete_but_late
            ),
            (2, 2, 1)
        );
        assert!(totals.missing_by_id.is_empty());
        assert!(totals.last_failure.as_ref().unwrap().missing_ids.is_empty());
        // Torque confirmation is outside the 56/15 telemetry statistics.
        trace.address = 40;
        trace.length = 1;
        trace.request_sent = true;
        totals.observe(&trace, Some("torque confirmation failed".into()));
        assert_eq!((totals.total_reads, totals.failed_reads), (2, 2));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn read_loss_preserves_ready_and_allows_hold_but_not_stale_torque_on() {
        use serialport::SerialPort;
        use std::sync::{
            Arc,
            atomic::{AtomicBool, AtomicUsize, Ordering},
        };
        let (mut master, mut slave) = serialport::TTYPort::pair().unwrap();
        master.set_timeout(Duration::from_millis(100)).unwrap();
        slave.set_timeout(Duration::from_millis(2)).unwrap();
        let done = Arc::new(AtomicBool::new(false));
        let drop_read = Arc::new(AtomicBool::new(false));
        let goals = Arc::new(AtomicUsize::new(0));
        let (exit, drop, writes) = (done.clone(), drop_read.clone(), goals.clone());
        let device = std::thread::spawn(move || {
            let mut torque = false;
            let mut positions = [2048u16; 256];
            let mut gains = [[32u8, 40u8]; 256];
            let mut sequence = 0u8;
            while !exit.load(Ordering::Relaxed) {
                let mut header = [0u8; 4];
                if master.read_exact(&mut header).is_err() {
                    continue;
                }
                let mut body = vec![0u8; header[3] as usize];
                master.read_exact(&mut body).unwrap();
                let address = body[1];
                let length = body[2] as usize;
                if body[0] == SYNC_WRITE {
                    for row in body[3..body.len() - 1].chunks_exact(length + 1) {
                        if address == 40 {
                            torque = row[1] != 0;
                        }
                        if address == 42 {
                            assert_eq!(length, 6);
                            positions[row[0] as usize] = u16::from_le_bytes([row[1], row[2]]);
                            assert_eq!(&row[3..7], &[0; 4]);
                            writes.fetch_add(1, Ordering::Relaxed);
                        }
                        if address == 50 {
                            gains[row[0] as usize].copy_from_slice(&row[1..3]);
                        }
                    }
                    continue;
                }
                if address == 56 && drop.load(Ordering::Relaxed) {
                    continue;
                }
                let ids = if body[0] == SYNC_READ {
                    body[3..body.len() - 1].to_vec()
                } else {
                    vec![header[2]]
                };
                sequence = sequence.wrapping_add(1);
                let mut responses = Vec::new();
                for id in ids {
                    let mut data = vec![0u8; length];
                    match (id, address) {
                        (IMU_ID, 0) => data.copy_from_slice(&IMU_IDENTITY),
                        (IMU_ID, 56) => {
                            data[7] = 0x30;
                            data[12] = sequence;
                        }
                        (_, 21) => data.copy_from_slice(&[32, 40, 0]),
                        (_, 33) => data[0] = 4,
                        (_, 40) => data[0] = u8::from(torque),
                        (_, 41) => {
                            data[1..3].copy_from_slice(&positions[id as usize].to_le_bytes())
                        }
                        (_, 42) => data.copy_from_slice(&positions[id as usize].to_le_bytes()),
                        (_, 50) => data[..2].copy_from_slice(&gains[id as usize]),
                        (_, 56) => {
                            data[..2].copy_from_slice(&2048u16.to_le_bytes());
                            data[6] = 73;
                            data[7] = 35;
                        }
                        _ => panic!("unexpected register {address}"),
                    }
                    responses.extend(packet(id, 0, &data).unwrap());
                }
                master.write_all(&responses).unwrap();
            }
        });
        let bus = Bus {
            port: Box::new(slave),
            timeout: Duration::from_millis(30),
            read_only: false,
            last_sync: SyncTrace::default(),
        };
        let mut io = FeetechIo::from_bus(bus, calibrated()).unwrap();
        for _ in 0..30 {
            io.read().unwrap();
        }
        assert!(io.imu_ready());
        io.set_torque(true).unwrap();
        let reads_before = io.telemetry.total_reads;
        drop_read.store(true, Ordering::Relaxed);
        let last = io.latest_sample_at;
        assert!(io.read().is_err());
        let totals = io.feetech_diagnostics().unwrap().telemetry;
        assert_eq!(
            (totals.total_reads, totals.failed_reads),
            (reads_before + 1, 1)
        );
        assert_eq!(totals.missing_by_id.len(), 16);
        assert!(totals.missing_by_id.values().all(|count| *count == 1));
        assert!(
            io.imu_ready(),
            "missing reply is not an IMU convergence reset"
        );
        assert_eq!(
            io.latest_sample_at, last,
            "old feedback must never be retimestamped as fresh"
        );
        io.latest_sample_at = Some(Instant::now() - Duration::from_millis(200));
        let before = goals.load(Ordering::Relaxed);
        io.write(&JointTargets::new([0.1; NUM_JOINTS])).unwrap();
        assert!(
            io.set_torque(true)
                .unwrap_err()
                .to_string()
                .contains("100 ms")
        );
        io.set_torque(false).unwrap(); // round trip also flushes the preceding goal packet
        assert_eq!(goals.load(Ordering::Relaxed) - before, NUM_JOINTS);
        assert_eq!(io.torque_state_confirmed, Some(false));
        for _ in 0..3 {
            let diagnostic = io.feetech_diagnostics().unwrap();
            assert_eq!(diagnostic.sync.address, 56);
            assert_eq!(diagnostic.sync.missing_ids.len(), 16);
            assert_eq!(diagnostic.telemetry.total_reads, reads_before + 1);
        }
        done.store(true, Ordering::Relaxed);
        device.join().unwrap();
    }

    fn telemetry_ids() -> Vec<u8> {
        std::iter::once(IMU_ID)
            .chain(crate::model::JOINT_IDS)
            .collect()
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn unified_imu_read_requires_all_16_frames_and_no_extra_transaction() {
        use serialport::SerialPort;
        for outcome in 0..4 {
            let (mut master, mut slave) = serialport::TTYPort::pair().unwrap();
            master.set_timeout(Duration::from_secs(1)).unwrap();
            slave.set_timeout(Duration::from_millis(2)).unwrap();
            let (finish, wait) = std::sync::mpsc::channel();
            let device = std::thread::spawn(move || {
                let mut request = [0; 24];
                master.read_exact(&mut request).unwrap();
                assert_eq!(
                    request.to_vec(),
                    sync_read_packet(56, 15, &telemetry_ids()).unwrap()
                );
                let mut responses = Vec::new();
                if outcome != 3 {
                    let mut imu = [0; 15];
                    imu[12] = 255;
                    let mut response =
                        packet(IMU_ID, if outcome == 2 { 4 } else { 0 }, &imu).unwrap();
                    if outcome == 1 {
                        *response.last_mut().unwrap() ^= 0x80;
                    }
                    responses.extend(response);
                }
                for id in crate::model::JOINT_IDS {
                    responses.extend(packet(id, 0, &[0; 15]).unwrap());
                }
                master.write_all(&responses).unwrap();
                wait.recv().unwrap();
                assert_eq!(master.bytes_to_read().unwrap(), 0);
            });
            let mut bus = Bus {
                port: Box::new(slave),
                timeout: Duration::from_millis(30),
                read_only: false,
                last_sync: SyncTrace::default(),
            };
            let result = bus.telemetry(&crate::model::JOINT_IDS);
            finish.send(()).unwrap();
            device.join().unwrap();
            assert_eq!(result.is_ok(), outcome == 0);

            assert_eq!(bus.last_sync.rx_bytes, if outcome == 3 { 315 } else { 336 });
            assert_eq!(bus.last_sync.bad_checksums, u64::from(outcome == 1));
            if outcome == 0 {
                let replies = result.unwrap();
                assert_eq!(replies.len(), 16);
                assert_eq!(replies[&IMU_ID].len(), 15);
            } else {
                assert_eq!(bus.last_sync.missing_ids, vec![IMU_ID]);
            }
        }
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn sync_torque_checks_all_fifteen_fragmented_replies_and_reports_missing() {
        use serialport::SerialPort;
        let (mut master, mut slave) = serialport::TTYPort::pair().unwrap();
        master.set_timeout(Duration::from_secs(1)).unwrap();
        slave.set_timeout(Duration::from_millis(2)).unwrap();
        let ids = crate::model::JOINT_IDS;
        let (finish, wait) = std::sync::mpsc::channel();
        let device = std::thread::spawn(move || {
            for attempt in 0..3 {
                let mut request = [0u8; 23];
                master.read_exact(&mut request).unwrap();
                assert_eq!(request.to_vec(), sync_read_packet(40, 1, &ids).unwrap());
                for (index, id) in ids.iter().enumerate() {
                    if attempt == 2 && index == 14 {
                        continue;
                    }
                    let value = u8::from(attempt == 1 && index == 14);
                    let response = packet(*id, 0, &[value]).unwrap();
                    for bytes in response.chunks(2) {
                        master.write_all(bytes).unwrap();
                    }
                }
            }
            wait.recv().unwrap();
        });
        let mut bus = Bus {
            port: Box::new(slave),
            timeout: Duration::from_millis(30),
            read_only: false,
            last_sync: SyncTrace::default(),
        };
        bus.verify_torque(&ids, false).unwrap();
        assert!(bus.last_sync.missing_ids.is_empty());

        assert!(
            bus.verify_torque(&ids, false)
                .unwrap_err()
                .to_string()
                .contains("not confirmed")
        );
        assert!(bus.verify_torque(&ids, false).is_err());
        assert_eq!(bus.last_sync.missing_ids, vec![ids[14]]);
        assert_eq!(bus.last_sync.missing_ids.len(), 1);

        finish.send(()).unwrap();
        device.join().unwrap();
    }
    #[test]
    fn verified_hat_read_and_reply() {
        assert_eq!(
            packet(1, READ, &[56, 11]).unwrap(),
            [255, 255, 1, 4, 2, 56, 11, 181]
        );
        let bytes = [
            255, 255, 1, 13, 0, 0x4d, 7, 0, 0, 0, 0, 59, 30, 0, 0, 0, 0x44,
        ];
        let mut d = Decoder::default();
        let s = bytes.into_iter().find_map(|b| d.push(b)).unwrap();
        let f = Feedback::decode(&s.data).unwrap();
        assert_eq!(f.position_raw, 1869);
        assert!((f.volts - 5.9).abs() < 1e-10);
        assert_eq!(f.temperature_c, 30);
        assert!(!f.moving);
    }
    #[test]
    fn rejects_damage_and_resynchronises() {
        let valid = packet(2, 0, &[7]).unwrap();
        let mut bad = valid.clone();
        *bad.last_mut().unwrap() ^= 1;
        let mut d = Decoder::default();
        for b in [8, 255, 0, 255, 255, 255].into_iter().chain(bad) {
            assert!(d.push(b).is_none());
        }
        let status = valid.into_iter().find_map(|b| d.push(b)).unwrap();
        assert_eq!(status.id, 2);
        assert_eq!(status.data, [7]);
    }
    #[test]
    fn fifteen_joint_sync_fits_single_native_packet() {
        let rows = (1..=15)
            .map(|id| (id, position_command(2048).unwrap().to_vec()))
            .collect::<Vec<_>>();
        let bytes = sync_write_packet(42, &rows).unwrap();
        assert_eq!(bytes.len(), 113);
        assert_eq!(bytes[2..7], [254, 109, 0x83, 42, 6]);
        assert_eq!(bytes[2..].iter().fold(0u8, |a, b| a.wrapping_add(*b)), 255);
    }
    #[test]
    fn combined_sync_read_packet_is_native_and_imu_first() {
        let bytes = sync_read_packet(56, 20, &[200, 1, 2]).unwrap();
        assert_eq!(bytes, [255, 255, 254, 7, 0x82, 56, 20, 200, 1, 2, 0x61]);
        assert!(sync_read_packet(56, 20, &[1, 200, 2]).is_err());
        assert!(sync_read_packet(56, 20, &[200, 1, 1]).is_err());
        assert!(sync_read_packet(250, 20, &[200]).is_err());
    }

    #[test]
    fn sync_read_collector_requires_each_exact_reply_once() {
        let mut pending = [1, 2].into_iter().collect::<BTreeSet<_>>();
        let mut replies = BTreeMap::new();
        assert!(
            !accept_sync_status(
                &mut pending,
                &mut replies,
                Status {
                    id: 2,
                    error: 0,
                    data: vec![2; 20],
                },
                20,
            )
            .unwrap()
        );
        assert!(
            accept_sync_status(
                &mut pending,
                &mut replies,
                Status {
                    id: 1,
                    error: 0,
                    data: vec![1; 20],
                },
                20,
            )
            .unwrap()
        );
        assert_eq!(replies.len(), 2);

        let mut pending = [1].into_iter().collect::<BTreeSet<_>>();
        let mut replies = BTreeMap::new();
        assert!(
            accept_sync_status(
                &mut pending,
                &mut replies,
                Status {
                    id: 2,
                    error: 0,
                    data: vec![0; 20],
                },
                20,
            )
            .is_err()
        );

        let mut pending = [1].into_iter().collect::<BTreeSet<_>>();
        let mut replies = BTreeMap::new();
        assert!(
            accept_sync_status(
                &mut pending,
                &mut replies,
                Status {
                    id: 1,
                    error: 0,
                    data: vec![0; 19],
                },
                20,
            )
            .is_err()
        );
    }
    #[test]
    fn validates_motion_before_send() {
        assert!(position_command(4096).is_err());
        assert_eq!(position_command(2048).unwrap(), [0, 8, 0, 0, 0, 0]);
        assert!(sync_write_packet(40, &[(1, vec![0]), (1, vec![0])]).is_err());
        assert!(sync_write_packet(40, &[(IMU_ID, vec![0])]).is_err());
    }
    #[test]
    fn sign_is_not_twos_complement() {
        assert_eq!(signed_magnitude(0x8064, 15), -100);
        assert_eq!(signed_magnitude(0x040a, 10), -10);
        assert_eq!(signed_magnitude(0x8000, 15), 0);
    }
    #[test]
    fn imu_layout_status_and_freshness_are_mandatory() {
        let mut raw = [0; 15];
        for sequence in [254, 255, 0, 1] {
            raw[12] = sequence;
            let sample = ImuSample::decode(&raw).unwrap();
            assert_eq!(sample.sequence, u32::from(sequence));
            assert!(sample.age_ms.is_none());
            assert_eq!(sample.age_upper_bound_ms, Some(30));
            assert!(sample.is_fresh(15_000));
            assert!(!sample.is_fresh(20_001));
        }
        for status in [1, 2, 4, 3, 6, 7] {
            raw[13] = status;
            assert!(!ImuSample::decode(&raw).unwrap().is_fresh(0));
        }
        raw[13] = 8; // slow reader is diagnostic, not fabricated sensor failure
        assert!(ImuSample::decode(&raw).unwrap().is_fresh(0));
        raw[13] = 16;
        assert!(ImuSample::decode(&raw).is_err());
        raw[13] = 0;
        raw[14] = 1;
        assert!(ImuSample::decode(&raw).is_err());
        assert!(ImuSample::decode(&[0; 20]).is_err());
        let mut diagnostic = [0; 20];
        diagnostic[12..16].copy_from_slice(&u32::MAX.to_le_bytes());
        diagnostic[16] = 9;
        diagnostic[18] = 1;
        diagnostic[19] = 1;
        let sample = ImuSample::decode_diagnostic(&diagnostic).unwrap();
        assert_eq!(sample.sequence, u32::MAX);
        assert_eq!(sample.age_ms, Some(9));
        assert!(sample.is_fresh(15_000));
        assert!(ImuSample::decode_diagnostic(&raw).is_err());
    }
    #[test]
    fn no_calibration_from_two_bench_ids() {
        let mut cal = Calibration::commissioning(crate::model::JOINT_IDS);
        cal.joints.truncate(2);
        assert!(cal.validate().is_err());
    }
    fn calibrated() -> Calibration {
        let mut cal = Calibration::commissioning(crate::model::JOINT_IDS);
        for joint in &mut cal.joints {
            joint.calibrated = true;
            joint.min_rad = Some(-1.5);
            joint.max_rad = Some(1.5);
        }
        cal.imu_mount_verified = true;
        cal.motion_enabled = true;
        cal
    }
    #[test]
    fn telemetry_config_does_not_implicitly_authorize_motion() {
        let mut cal = Calibration::commissioning(crate::model::JOINT_IDS);
        assert!(cal.validate().is_ok());
        assert!(cal.validate_motion().is_err());
        cal.motion_enabled = true;
        assert!(cal.validate().is_err());
        let mut cal = calibrated();
        assert!(cal.validate_motion().is_ok());
        assert!(
            !cal.units_verified,
            "native velocity requires no per-robot conversion setting"
        );
        cal.joints[3].calibrated = false;
        assert!(cal.validate_motion().is_err());
    }
    #[test]
    fn rejects_joint_order_and_limits_before_bus_open() {
        let mut cal = calibrated();
        cal.joints.swap(0, 1);
        assert!(cal.validate().is_err());
        let mut cal = calibrated();
        cal.joints[0].min_rad = Some(-4.0);
        assert!(cal.validate().is_err());
        let mut cal = calibrated();
        cal.joints[2].min_rad = Some(0.0);
        assert!(
            cal.validate().is_err(),
            "official home must fit the measured range"
        );
        let mut cal = calibrated();
        cal.imu_mount_quat = [2.0, 0.0, 0.0, 0.0];
        assert!(cal.validate().is_err());
    }
    #[test]
    fn calibrated_target_roundtrips_and_clamps_without_wrapping() {
        let mut joint = calibrated().joints.remove(0);
        joint.zero_raw = 1900;
        for direction in [-1, 1] {
            joint.direction = direction;
            let (raw, limited) = joint.target_raw(0.6).unwrap();
            assert!(!limited);
            assert!((joint.position_rad(i32::from(raw)) - 0.6).abs() <= TAU / 8192.0);
            let (raw, limited) = joint.target_raw(9.0).unwrap();
            assert!(limited);
            assert!((joint.position_rad(i32::from(raw)) - 1.5).abs() <= TAU / 8192.0);
            assert!(joint.target_raw(f64::NAN).is_err());
        }
    }
}

#[cfg(all(test, unix))]
mod hd1910_transport_tests {
    use super::*;
    use serialport::SerialPort;
    use std::sync::atomic::{AtomicU64, AtomicUsize};
    use std::sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    };

    // Stall the return of an already-complete serial read, as a descheduled host
    // can do. Delaying the device response instead would merely hit the unchanged
    // 20 ms wait limit and would not exercise the complete-but-late branch.
    struct ReadStallPort {
        inner: Box<dyn SerialPort>,
        stall_us: Arc<AtomicU64>,
        received: AtomicUsize,
        reply_bytes: usize,
    }
    impl std::io::Read for ReadStallPort {
        fn read(&mut self, out: &mut [u8]) -> std::io::Result<usize> {
            let n = self.inner.read(out)?;
            let total = self.received.fetch_add(n, Ordering::Relaxed) + n;
            if n > 0 && total >= self.reply_bytes {
                let us = self.stall_us.swap(0, Ordering::Relaxed);
                if us != 0 {
                    std::thread::sleep(Duration::from_micros(us));
                }
            }
            Ok(n)
        }
    }
    impl std::io::Write for ReadStallPort {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            self.inner.write(bytes)
        }
        fn flush(&mut self) -> std::io::Result<()> {
            self.inner.flush()
        }
    }
    macro_rules! forward_port {
        () => {};
        (fn $name:ident(&self $(, $arg:ident: $ty:ty)*) -> $ret:ty; $($rest:tt)*) => {
            fn $name(&self $(, $arg: $ty)*) -> $ret {
                self.inner.$name($($arg),*)
            }
            forward_port!($($rest)*);
        };
        (fn $name:ident(&mut self $(, $arg:ident: $ty:ty)*) -> $ret:ty; $($rest:tt)*) => {
            fn $name(&mut self $(, $arg: $ty)*) -> $ret {
                self.inner.$name($($arg),*)
            }
            forward_port!($($rest)*);
        };
    }
    impl SerialPort for ReadStallPort {
        forward_port! {
            fn name(&self) -> Option<String>;
            fn baud_rate(&self) -> serialport::Result<u32>;
            fn data_bits(&self) -> serialport::Result<serialport::DataBits>;
            fn flow_control(&self) -> serialport::Result<serialport::FlowControl>;
            fn parity(&self) -> serialport::Result<serialport::Parity>;
            fn stop_bits(&self) -> serialport::Result<serialport::StopBits>;
            fn timeout(&self) -> Duration;
            fn set_baud_rate(&mut self, rate: u32) -> serialport::Result<()>;
            fn set_data_bits(&mut self, bits: serialport::DataBits) -> serialport::Result<()>;
            fn set_flow_control(&mut self, flow: serialport::FlowControl) -> serialport::Result<()>;
            fn set_parity(&mut self, parity: serialport::Parity) -> serialport::Result<()>;
            fn set_stop_bits(&mut self, bits: serialport::StopBits) -> serialport::Result<()>;
            fn set_timeout(&mut self, timeout: Duration) -> serialport::Result<()>;
            fn write_request_to_send(&mut self, level: bool) -> serialport::Result<()>;
            fn write_data_terminal_ready(&mut self, level: bool) -> serialport::Result<()>;
            fn read_clear_to_send(&mut self) -> serialport::Result<bool>;
            fn read_data_set_ready(&mut self) -> serialport::Result<bool>;
            fn read_ring_indicator(&mut self) -> serialport::Result<bool>;
            fn read_carrier_detect(&mut self) -> serialport::Result<bool>;
            fn bytes_to_read(&self) -> serialport::Result<u32>;
            fn bytes_to_write(&self) -> serialport::Result<u32>;
            fn set_break(&self) -> serialport::Result<()>;
            fn clear_break(&self) -> serialport::Result<()>;
        }
        fn clear(&self, buffer: serialport::ClearBuffer) -> serialport::Result<()> {
            self.received.store(0, Ordering::Relaxed);
            self.inner.clear(buffer)
        }
        fn try_clone(&self) -> serialport::Result<Box<dyn SerialPort>> {
            Ok(Box::new(Self {
                inner: self.inner.try_clone()?,
                stall_us: self.stall_us.clone(),
                received: AtomicUsize::new(0),
                reply_bytes: self.reply_bytes,
            }))
        }
    }
    fn stall_reads(bus: Bus, reply_bytes: usize) -> (Bus, Arc<AtomicU64>) {
        let stall_us = Arc::new(AtomicU64::new(0));
        let port = Box::new(ReadStallPort {
            inner: bus.port,
            stall_us: stall_us.clone(),
            received: AtomicUsize::new(0),
            reply_bytes,
        });
        (Bus { port, ..bus }, stall_us)
    }
    #[derive(Clone, Default)]
    struct Faults {
        missing: Vec<u8>,
        checksum_id: Option<u8>,
        status_id: Option<u8>,
        imu_stale: bool,
    }
    struct Emulator {
        faults: Arc<Mutex<Faults>>,
        done: Arc<AtomicBool>,
        regs: Arc<Mutex<Vec<[u8; 96]>>>,
        writes: Arc<Mutex<Vec<(u8, u8, Vec<u8>)>>>,
        thread: Option<std::thread::JoinHandle<()>>,
    }
    impl Drop for Emulator {
        fn drop(&mut self) {
            self.done.store(true, Ordering::Relaxed);
            self.thread.take().unwrap().join().unwrap();
        }
    }
    fn emulator(reject_gain: bool) -> (Bus, Emulator) {
        let (mut master, mut slave) = serialport::TTYPort::pair().unwrap();
        master.set_timeout(Duration::from_millis(20)).unwrap();
        slave.set_timeout(Duration::from_millis(2)).unwrap();
        let regs = Arc::new(Mutex::new(vec![[0u8; 96]; 256]));
        for reg in regs.lock().unwrap().iter_mut() {
            reg[21..24].copy_from_slice(&[32, 40, 0]);
            reg[33] = 4;
            reg[41] = 64;
            reg[42..44].copy_from_slice(&2048u16.to_le_bytes());
            reg[44..46].copy_from_slice(&500u16.to_le_bytes());
            reg[46] = 100;
            reg[48..50].copy_from_slice(&1000u16.to_le_bytes());
            reg[50..53].copy_from_slice(&[32, 40, 0]);
            reg[56..58].copy_from_slice(&2048u16.to_le_bytes());
            reg[62] = 74;
            reg[63] = 35;
        }
        let faults = Arc::new(Mutex::new(Faults::default()));
        let fault_source = faults.clone();
        let done = Arc::new(AtomicBool::new(false));
        let writes = Arc::new(Mutex::new(Vec::new()));
        let (d, r, w) = (done.clone(), regs.clone(), writes.clone());
        let thread = std::thread::spawn(move || {
            let mut seq = 0u8;
            while !d.load(Ordering::Relaxed) {
                let mut header = [0u8; 4];
                if master.read_exact(&mut header).is_err() {
                    continue;
                }
                let mut body = vec![0u8; header[3] as usize];
                master.read_exact(&mut body).unwrap();
                let addr = body[1];
                let len = body[2] as usize;
                if body[0] == SYNC_WRITE {
                    for row in body[3..body.len() - 1].chunks_exact(len + 1) {
                        let id = row[0];
                        w.lock().unwrap().push((id, addr, row[1..].to_vec()));
                        if reject_gain
                            && id == 22
                            && ((addr == 50 && row[1] == 5) || (addr == 48 && row[3] == 3))
                        {
                            continue;
                        }
                        r.lock().unwrap()[id as usize][addr as usize..addr as usize + len]
                            .copy_from_slice(&row[1..]);
                    }
                    continue;
                }
                let ids = if body[0] == SYNC_READ {
                    body[3..body.len() - 1].to_vec()
                } else {
                    vec![header[2]]
                };
                seq = seq.wrapping_add(1);
                let mut replies = Vec::new();
                let fault = fault_source.lock().unwrap().clone();
                for id in ids {
                    if addr == 56 && fault.missing.contains(&id) {
                        continue;
                    }
                    let mut data = if id == IMU_ID {
                        vec![0; len]
                    } else {
                        r.lock().unwrap()[id as usize][addr as usize..addr as usize + len].to_vec()
                    };
                    if id == IMU_ID && addr == 0 {
                        data.copy_from_slice(&IMU_IDENTITY);
                    }
                    if id == IMU_ID && addr == 56 {
                        data[7] = 0x30;
                        data[12] = seq;
                        if fault.imu_stale {
                            data[13] = 1;
                        }
                    }
                    let status = if addr == 56 && fault.status_id == Some(id) {
                        4
                    } else {
                        0
                    };
                    let mut response = packet(id, status, &data).unwrap();
                    if addr == 56 && fault.checksum_id == Some(id) {
                        *response.last_mut().unwrap() ^= 1;
                    }
                    replies.extend(response);
                }
                master.write_all(&replies).unwrap();
            }
        });
        (
            Bus {
                port: Box::new(slave),
                timeout: Duration::from_millis(30),
                read_only: false,
                last_sync: SyncTrace::default(),
            },
            Emulator {
                faults,
                done,
                regs,
                writes,
                thread: Some(thread),
            },
        )
    }
    fn calibration() -> Calibration {
        let mut c = Calibration::commissioning(crate::model::JOINT_IDS);
        for j in &mut c.joints {
            j.calibrated = true;
            j.min_rad = Some(-1.5);
            j.max_rad = Some(1.5);
        }
        c.motion_enabled = true;
        c.imu_mount_verified = true;
        c
    }

    #[test]
    fn control_status_matches_full_diagnostics_through_feedback_and_torque_changes() {
        // The allocation-free HOME flags must retain the old guard's verdicts,
        // including no sample, unconfirmed torque and wall-clock feedback holds.
        let (bus, device) = emulator(false);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        let check = |io: &FeetechIo| {
            let full = io.feetech_diagnostics().unwrap();
            let status = io.feetech_control_status().unwrap();
            assert_eq!(status, FeetechControlStatus::from(&full));
            status
        };
        assert!(!check(&io).all_joints_fresh);
        for _ in 0..30 {
            io.read().unwrap();
        }
        let ready = check(&io);
        assert!(ready.all_joints_fresh && ready.imu_ready && !ready.joints_held);
        assert_eq!(ready.torque_state_confirmed, Some(false));
        io.set_torque(true).unwrap();
        assert_eq!(check(&io).torque_state_confirmed, Some(true));
        let i = index(22);
        for missing in 1..=4 {
            io.joint_missing[i] = missing;
            let status = check(&io);
            assert!(!status.all_joints_fresh);
            assert_eq!(status.joints_held, missing > JOINT_COAST_TICKS);
        }
        io.read().unwrap();
        assert!(check(&io).all_joints_fresh);
        io.joint_feedback[i].as_mut().unwrap().at = Instant::now() - Duration::from_millis(200);
        assert!(check(&io).joints_held);
        io.torque_state_confirmed = None;
        assert_eq!(check(&io).torque_state_confirmed, None);
        io.read().unwrap();
        io.set_torque(false).unwrap();
        assert_eq!(check(&io).torque_state_confirmed, Some(false));
        let writes = device.writes.lock().unwrap().len();
        let reads = io.telemetry.total_reads;
        let io = crate::hardware::HardwareIo::Feetech(io);
        let safety = crate::safety::Safety::new(io, Default::default());
        assert_eq!(
            safety.feetech_control_status().unwrap(),
            FeetechControlStatus::from(&safety.feetech_diagnostics().unwrap())
        );
        assert_eq!(device.writes.lock().unwrap().len(), writes);
        assert_eq!(
            safety.feetech_diagnostics().unwrap().telemetry.total_reads,
            reads
        );
    }

    #[test]
    fn diagnostic_registers_share_storage_and_refresh_only_after_a_new_inspection() {
        // Sharing must preserve the before-arm snapshot held by an older frame,
        // while a later inspection and dynamic torque flags reach new frames.
        let (bus, device) = emulator(false);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        let before = io.feetech_diagnostics().unwrap();
        io.torque_state_confirmed = None;
        let next = io.feetech_diagnostics().unwrap();
        assert!(Arc::ptr_eq(
            &before.hd1910.registers_before_arm,
            &next.hd1910.registers_before_arm
        ));
        assert_eq!(before.torque_state_confirmed, Some(false));
        assert_eq!(next.torque_state_confirmed, None);
        let wire = serde_json::to_value(&next).unwrap();
        assert_eq!(
            wire["hd1910"]["registers_before_arm"],
            serde_json::to_value(before.hd1910.registers_before_arm.as_ref()).unwrap()
        );
        device.regs.lock().unwrap()[22][50..53].copy_from_slice(&[7, 8, 9]);
        io.hd1910.inspect(&mut io.bus, &io.calibration).unwrap();
        let after = io.feetech_diagnostics().unwrap();
        assert!(!Arc::ptr_eq(
            &before.hd1910.registers_before_arm,
            &after.hd1910.registers_before_arm
        ));
        assert_eq!(
            before.hd1910.registers_before_arm[index(22)].temporary_pdi,
            [32, 40, 0]
        );
        assert_eq!(
            after.hd1910.registers_before_arm[index(22)].temporary_pdi,
            [7, 8, 9]
        );
        assert!(device.writes.lock().unwrap().is_empty());
    }

    #[test]
    fn numeric_snapshot_matches_native_report_without_uart_or_lost_offline_counts() {
        // The new reporting hand-off must preserve every old diagnostic member,
        // including held joints and post-command torque, without touching the bus.
        let (bus, device) = emulator(false);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        let compare = |io: &FeetechIo| {
            let old = io.feetech_diagnostics().unwrap();
            let snapshot = io.feetech_snapshot().unwrap();
            let mut expected = serde_json::to_value(&old).unwrap();
            let mut actual = serde_json::to_value(snapshot.metadata.as_ref()).unwrap();
            actual.as_object_mut().unwrap().extend(
                serde_json::to_value(&snapshot.dynamic)
                    .unwrap()
                    .as_object()
                    .unwrap()
                    .clone(),
            );
            actual["hd1910"] = serde_json::to_value(&snapshot.hd1910).unwrap();
            // Both APIs timestamp at their own call. Compare the measured ages
            // separately rather than making a scheduler-dependent equality test.
            for key in ["sample_age_ms"] {
                if let (Some(a), Some(b)) = (actual[key].as_u64(), expected[key].as_u64()) {
                    assert!(a >= b && a - b < 100);
                }
                actual.as_object_mut().unwrap().remove(key);
                expected.as_object_mut().unwrap().remove(key);
            }
            for (a, b) in actual["joints"]
                .as_array_mut()
                .unwrap()
                .iter_mut()
                .zip(expected["joints"].as_array_mut().unwrap())
            {
                assert!(
                    a["sample_age_ms"].as_u64().unwrap() >= b["sample_age_ms"].as_u64().unwrap()
                );
                a.as_object_mut().unwrap().remove("sample_age_ms");
                b.as_object_mut().unwrap().remove("sample_age_ms");
            }
            assert_eq!(actual, expected);
            snapshot
        };
        let before = compare(&io);
        // No reporter exists while acquisition continues: history must still grow.
        for _ in 0..3 {
            io.read().unwrap();
        }
        let ready = compare(&io);
        assert_eq!(
            ready.dynamic.telemetry.total_reads,
            before.dynamic.telemetry.total_reads + 3
        );
        assert!(Arc::ptr_eq(&before.metadata, &ready.metadata));
        let i = index(22);
        io.joint_missing[i] = 4;
        io.joint_missing_total[i] = 7;
        io.joint_feedback[i].as_mut().unwrap().at = Instant::now() - Duration::from_secs(1);
        assert!(!compare(&io).dynamic.all_joints_fresh);
        io.torque_state_confirmed = None;
        assert_eq!(compare(&io).dynamic.torque_state_confirmed, None);
        io.torque_state_confirmed = Some(false);
        assert_eq!(compare(&io).dynamic.torque_state_confirmed, Some(false));
        let writes = device.writes.lock().unwrap().len();
        let reads = io.telemetry.total_reads;
        let safety = crate::safety::Safety::new(
            crate::hardware::HardwareIo::Feetech(io),
            Default::default(),
        );
        assert_eq!(
            safety
                .feetech_snapshot()
                .unwrap()
                .dynamic
                .telemetry
                .total_reads,
            reads
        );
        assert_eq!(safety.feetech_sync_trace().unwrap().address, 56);
        assert_eq!(device.writes.lock().unwrap().len(), writes);
    }

    #[test]
    fn both_hip_pitch_signed_replies_reach_sensors_and_diagnostics() {
        let (bus, device) = emulator(false);
        let c = calibration();
        for id in [12, 22] {
            device.regs.lock().unwrap()[id][56..58].copy_from_slice(&34180u16.to_le_bytes());
        }
        let mut io = FeetechIo::from_bus(bus, c.clone()).unwrap();
        for _ in 0..3 {
            let sensors = io.read().unwrap();
            let diag = io.feetech_diagnostics().unwrap();
            for id in [12, 22] {
                let i = c.joints.iter().position(|j| j.id == id).unwrap();
                assert_eq!(sensors.positions[i], c.joints[i].position_rad(-1412));
                let row = diag.joints.iter().find(|j| j.id == id).unwrap();
                assert_eq!(
                    (
                        row.position_wire_raw,
                        row.position_signed_raw,
                        row.position_raw
                    ),
                    (34180, -1412, -1412)
                );
                assert!(row.feedback_fresh);
            }
        }
        device.regs.lock().unwrap()[22][56..58].copy_from_slice(&0xffffu16.to_le_bytes());
        let sensors = io.read().unwrap();
        assert_eq!(
            sensors.positions[index(22)],
            c.joints[index(22)].position_rad(-32767)
        );
        let row = io
            .feetech_diagnostics()
            .unwrap()
            .joints
            .into_iter()
            .find(|j| j.id == 22)
            .unwrap();
        assert_eq!(
            (
                row.position_wire_raw,
                row.position_signed_raw,
                row.position_raw
            ),
            (65535, -32767, -32767)
        );
    }

    #[test]
    fn negative_feedback_preloads_itself_but_home_targets_stay_calibrated_positive() {
        let (bus, device) = emulator(false);
        let mut c = calibration();
        c.joints[index(22)].zero_raw = 1977;
        c.joints[index(22)].direction = -1;
        c.joints[index(12)].zero_raw = 1799;
        c.joints[index(12)].direction = -1;
        for (id, position) in [(22, -1670), (12, -1), (30, 6244), (31, -6048)] {
            device.regs.lock().unwrap()[id][56..58]
                .copy_from_slice(&signed_position_word(position).unwrap().to_le_bytes());
        }
        let mut io = FeetechIo::from_bus(bus, c.clone()).unwrap();
        let mut measured = Sensors::default();
        for _ in 0..30 {
            measured = io.read().unwrap();
        }
        device.writes.lock().unwrap().clear();
        io.set_torque(true).unwrap();
        let ids = crate::model::JOINT_IDS;
        let goals = io.bus.sync_read(42, 6, &ids).unwrap();
        for (id, position) in [(22, -1670), (12, -1), (30, 6244), (31, -6048)] {
            let goal = &goals[&(id as u8)];
            assert_eq!(
                signed_magnitude(u16::from_le_bytes([goal[0], goal[1]]), 15),
                position
            );
            assert_eq!(goal[2..], [0, 0, 0, 0]);
        }
        {
            let writes = device.writes.lock().unwrap();
            let first_on = writes
                .iter()
                .position(|(_, address, data)| *address == 40 && data[0] == 1)
                .unwrap();
            for id in ids {
                assert!(
                    writes[..first_on]
                        .iter()
                        .any(|(target, address, _)| *target == id && *address == 42)
                );
            }
        }
        // Exercise the HOME-shaped path through the real writer. Mechanical limits
        // still apply, but negative feedback must never select a different target turn.
        let start = measured.positions;
        for step in 0..=50 {
            let target = std::array::from_fn(|i| {
                start[i] + (crate::model::DEFAULT_POSITION[i] - start[i]) * f64::from(step) / 50.0
            });
            io.write(&JointTargets::new(target)).unwrap();
            let goals = io.bus.sync_read(42, 6, &ids).unwrap();
            for (i, id) in ids.into_iter().enumerate() {
                let expected = c.joints[i].target_raw(target[i]).unwrap().0;
                assert_eq!(goals[&id][..2], expected.to_le_bytes());
                assert_eq!(goals[&id][2..], [0, 0, 0, 0]);
            }
        }
        let goals = io.bus.sync_read(42, 2, &ids).unwrap();
        assert_eq!(goals[&22], 2276u16.to_le_bytes());
        assert_eq!(goals[&12], 1500u16.to_le_bytes());
        assert!(
            device
                .writes
                .lock()
                .unwrap()
                .iter()
                .all(|(_, address, _)| [40, 42, 50].contains(address))
        );
        // A different raw revolution on re-arm or service restart never changes HOME.
        io.set_torque(false).unwrap();
        device.regs.lock().unwrap()[22][56..58]
            .copy_from_slice(&signed_position_word(-1820).unwrap().to_le_bytes());
        io.read().unwrap();
        io.set_torque(true).unwrap();
        io.write(&JointTargets::new(crate::model::DEFAULT_POSITION))
            .unwrap();
        assert_eq!(
            io.bus.sync_read(42, 2, &ids).unwrap()[&22],
            2276u16.to_le_bytes()
        );
        let mut restarted = FeetechIo::from_bus(io.bus, c).unwrap();
        for _ in 0..30 {
            measured = restarted.read().unwrap();
        }
        device.writes.lock().unwrap().clear();
        restarted
            .write(&JointTargets::new(measured.positions))
            .unwrap();
        assert!(device.writes.lock().unwrap().is_empty());
        restarted.set_torque(true).unwrap();
        restarted
            .write(&JointTargets::new(crate::model::DEFAULT_POSITION))
            .unwrap();
        let goals = restarted.bus.sync_read(42, 2, &ids).unwrap();
        assert_eq!(goals[&22], 2276u16.to_le_bytes());
        assert_eq!(goals[&12], 1500u16.to_le_bytes());
    }

    #[test]
    fn telemetry_between_old_and_new_deadline_is_fresh_without_late_exception() {
        let (bus, device) = emulator(false);
        let (bus, stall) = stall_reads(bus, 336);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        let before = io.read().unwrap();
        set_positions(&device, 2100);
        stall.store(16_000, Ordering::Relaxed);
        let after = io.read().unwrap();
        let diag = io.feetech_diagnostics().unwrap();
        assert_ne!(before.positions, after.positions);
        assert!(!diag.sync.complete_but_late && !diag.sync.deadline_exceeded);
        assert!((15_000..20_000).contains(&diag.sync.elapsed_us));
        assert!(diag.sync.missing_ids.is_empty());
        assert_eq!(diag.telemetry.complete_but_late, 0);
        assert_eq!(diag.telemetry.failed_reads, 0);
        assert!(diag.telemetry.last_error.is_none());
        assert!(diag.telemetry.last_failure.is_none());
    }

    #[test]
    fn complete_late_telemetry_still_rejects_expired_data_and_bad_imu() {
        let (bus, device) = emulator(false);
        let (bus, stall) = stall_reads(bus, 336);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        io.read().unwrap();
        let before = io.latest_sample_at;
        stall.store(22_000, Ordering::Relaxed);
        assert!(
            io.read()
                .unwrap_err()
                .to_string()
                .contains("complete but transaction deadline exceeded")
        );
        assert_eq!(io.latest_sample_at, before);
        let diag = io.feetech_diagnostics().unwrap();
        assert_eq!(diag.telemetry.failed_reads, 1);
        assert_eq!(diag.telemetry.complete_but_late, 1);
        assert_eq!(diag.telemetry.accepted_complete_but_late, 0);
        assert!(!diag.telemetry.last_complete_but_late.unwrap().accepted);
        assert!(diag.telemetry.last_failure.unwrap().elapsed_us >= 20_000);
        assert!(diag.telemetry.missing_by_id.is_empty());
        device.faults.lock().unwrap().imu_stale = true;
        stall.store(15_200, Ordering::Relaxed);
        assert!(
            io.read()
                .unwrap_err()
                .to_string()
                .contains("IMU not ready or stale")
        );
        assert_eq!(io.latest_sample_at, before);
    }

    #[test]
    fn complete_late_torque_confirmation_keeps_its_original_deadline() {
        let (bus, _device) = emulator(false);
        let (mut bus, stall) = stall_reads(bus, 105);
        stall.store(15_200, Ordering::Relaxed);
        assert!(
            bus.verify_torque(&crate::model::JOINT_IDS, false)
                .unwrap_err()
                .to_string()
                .contains("complete but transaction deadline exceeded")
        );
        assert!(bus.last_sync.complete_but_late);
    }
    #[test]
    fn hd1910_arm_goals_and_relax_preserve_acceleration_and_eeprom() {
        let (mut bus, device) = emulator(false);
        // Same writer used by commissioning before switching to the motion loop.
        // Every servo retains its own existing acceleration, not a fixed test value.
        for id in crate::model::JOINT_IDS {
            device.regs.lock().unwrap()[id as usize][41] = id * 3;
            bus.positions(&[(id, 2048)]).unwrap();
        }
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        assert_eq!(io.hd1910.diagnostics().registers_before_arm.len(), 15);
        for _ in 0..30 {
            io.read().unwrap();
        }
        io.set_torque(true).unwrap();
        io.write(&JointTargets::new([0.1; NUM_JOINTS])).unwrap();
        for id in crate::model::JOINT_IDS {
            let reg = device.regs.lock().unwrap()[id as usize];
            assert_eq!(reg[50], if id == 34 { 10 } else { 5 });
            assert_eq!(reg[51], 20);
        }
        io.set_torque(false).unwrap();
        for id in crate::model::JOINT_IDS {
            let reg = device.regs.lock().unwrap()[id as usize];
            assert_eq!(reg[40], 0);
            assert_eq!(reg[41], id * 3);
            assert_eq!(&reg[21..24], &[32, 40, 0]);
            assert_eq!(&reg[50..53], &[32, 40, 0]);
            assert_eq!(&reg[46..48], &[0, 0]);
        }
        let writes = device.writes.lock().unwrap();
        assert!(writes.iter().all(|(_, a, _)| [40, 42, 50].contains(a)));
        assert!(
            writes
                .iter()
                .filter(|(_, a, _)| *a == 42)
                .all(|(_, _, p)| p.len() == 6 && p[2..] == [0, 0, 0, 0])
        );
        assert!(!io.hd1910.diagnostics().restore_pending);
    }
    #[test]
    fn console_servo_test_writes_all_fifteen_then_restores_without_eeprom_or_motion_changes() {
        let (bus, device) = emulator(false);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        let parameters = crate::hd1910_test::Parameters {
            kp: 3,
            kd: 0,
            torque_limit: 681,
        };
        io.hd1910.test_parameters = Some(parameters);
        assert!(
            device.writes.lock().unwrap().is_empty(),
            "editing/loading settings must not write motors"
        );
        for _ in 0..30 {
            io.read().unwrap();
        }
        for _ in 0..2 {
            io.set_torque(true).unwrap();
            // The official gain caller and model switches must not overwrite HD1910 test values.
            io.set_gain(200).unwrap();
            for id in crate::model::JOINT_IDS {
                let reg = device.regs.lock().unwrap()[id as usize];
                assert_eq!(&reg[48..52], &[0xa9, 0x02, 3, 0]);
                assert_eq!(&reg[21..24], &[32, 40, 0]);
                assert_eq!(reg[52], 0);
                assert_eq!(reg[41], 64);
            }
            let diagnostic = io.hd1910.diagnostics();
            assert_eq!(diagnostic.servo_parameters, Some(parameters));
            assert!(diagnostic.temporary_gains_applied);
            io.set_torque(false).unwrap();
            for id in crate::model::JOINT_IDS {
                let reg = device.regs.lock().unwrap()[id as usize];
                assert_eq!(&reg[48..53], &[0xe8, 0x03, 32, 40, 0]);
            }
            assert!(!io.hd1910.diagnostics().restore_pending);
        }
        assert!(
            device
                .writes
                .lock()
                .unwrap()
                .iter()
                .all(|(_, a, _)| [40, 42, 48].contains(a))
        );
    }

    #[test]
    fn console_servo_test_partial_write_remains_restorable() {
        let (bus, device) = emulator(true);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        io.hd1910.test_parameters = Some(crate::hd1910_test::Parameters {
            kp: 3,
            kd: 0,
            torque_limit: 681,
        });
        for _ in 0..30 {
            io.read().unwrap();
        }
        assert!(
            io.set_torque(true)
                .unwrap_err()
                .to_string()
                .contains("ID 22")
        );
        assert!(io.hd1910.diagnostics().restore_pending);
        assert!(
            !device
                .writes
                .lock()
                .unwrap()
                .iter()
                .any(|(_, a, v)| *a == 40 && v[0] == 1)
        );
        io.set_torque(false).unwrap();
        for id in crate::model::JOINT_IDS {
            assert_eq!(
                &device.regs.lock().unwrap()[id as usize][48..53],
                &[0xe8, 0x03, 32, 40, 0]
            );
        }
    }

    #[test]
    fn hd1910_gain_readback_failure_never_enables_torque_and_remains_restorable() {
        let (bus, device) = emulator(true);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        for _ in 0..30 {
            io.read().unwrap();
        }
        let result = io.set_torque(true).unwrap_err().to_string();
        assert!(result.contains("ID 22"), "{result}");
        assert!(io.hd1910.diagnostics().restore_pending);
        assert!(
            !device
                .writes
                .lock()
                .unwrap()
                .iter()
                .any(|(_, a, v)| *a == 40 && v[0] == 1)
        );
        io.set_torque(false).unwrap();
        for id in crate::model::JOINT_IDS {
            assert_eq!(
                &device.regs.lock().unwrap()[id as usize][50..53],
                &[32, 40, 0]
            );
        }
    }

    fn set_positions(device: &Emulator, raw: u16) {
        for id in crate::model::JOINT_IDS {
            device.regs.lock().unwrap()[id as usize][56..58].copy_from_slice(&raw.to_le_bytes());
        }
    }
    fn index(id: u8) -> usize {
        crate::model::JOINT_IDS
            .iter()
            .position(|v| *v == id)
            .unwrap()
    }

    #[test]
    fn native_speed_reaches_policy_with_signed_magnitude_local_directions_and_no_current_claim() {
        use crate::obs::{ACTION_LEN, Command, Observation};
        let (bus, device) = emulator(false);
        let mut c = calibration();
        let wire: [u16; NUM_JOINTS] = [
            0, 0x8000, 1, 0x8001, 0x7fff, 0xffff, 13, 0x800d, 64, 0x8040, 7, 0x8007, 123, 0x807b, 2,
        ];
        // These are signed-magnitude values, NOT i16 two's-complement.
        let signed = [
            0, 0, 1, -1, 32767, -32767, 13, -13, 64, -64, 7, -7, 123, -123, 2,
        ];
        for (i, j) in c.joints.iter_mut().enumerate() {
            j.direction = if i % 2 == 0 { 1 } else { -1 };
            // Distinct zero points must have no effect on velocity.
            j.zero_raw = 1800 + i as u16 * 9;
            device.regs.lock().unwrap()[j.id as usize][58..60]
                .copy_from_slice(&wire[i].to_le_bytes());
        }
        assert!(!c.units_verified);
        let expected: [f64; NUM_JOINTS] = std::array::from_fn(|i| {
            (f64::from(signed[i]) * 4.39453125).to_radians() * f64::from(c.joints[i].direction)
        });
        let mut io = FeetechIo::from_bus(bus, c).unwrap();
        // First sample already has speed, despite having no position history.
        let first = io.read().unwrap();
        for (i, want) in expected.iter().enumerate() {
            assert!((first.velocities[i] - want).abs() < 1e-10, "joint {i}");
            assert!(first.currents_ma[i].is_nan());
        }
        let obs = Observation::build(
            &first.imu,
            &first.positions,
            &first.velocities,
            &crate::model::DEFAULT_POSITION,
            &[0.; ACTION_LEN],
            &Command::default(),
        );
        let expected_policy: Vec<_> = expected
            .iter()
            .enumerate()
            .filter(|(i, _)| *i != crate::model::MOUTH_INDEX)
            .map(|(_, v)| *v as f32)
            .collect();
        assert_eq!(&obs.as_slice()[20..34], expected_policy.as_slice());
        let diag = io.feetech_diagnostics().unwrap();
        assert_eq!(diag.velocity_source, crate::hd1910::VELOCITY_SOURCE);
        assert!((diag.velocity_rad_s_per_count.unwrap() - 0.07669903939428206).abs() < 1e-15);
        assert!(!diag.current_available);
        assert!(!io.calibration.units_verified);
        // A large position change cannot manufacture speed when native speed is zero.
        set_positions(&device, 2200);
        for id in crate::model::JOINT_IDS {
            device.regs.lock().unwrap()[id as usize][58..60].copy_from_slice(&[0, 0]);
        }
        io.hd1910 = crate::hd1910::State::default();
        let stopped = io.read().unwrap();
        assert_eq!(stopped.velocities, [0.; NUM_JOINTS]);
        assert_ne!(stopped.positions, first.positions);
    }

    #[test]
    fn twenty_ms_missing_replies_keep_failure_identity_and_never_refresh_expired_imu() {
        let (bus, device) = emulator(false);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        for _ in 0..30 {
            io.read().unwrap();
        }
        io.set_torque(true).unwrap();
        for id in crate::model::JOINT_IDS {
            let before = io.latest_sample_at;
            let joint_time = io.joint_feedback[index(id)].as_ref().unwrap().at;
            device.faults.lock().unwrap().missing = vec![id];
            // FT6 only reports an age upper bound of 30 ms. Waiting the full
            // 20 ms consumes the 50 ms cap: reject, then let upstream coast.
            assert!(
                io.read()
                    .unwrap_err()
                    .to_string()
                    .contains("IMU not ready or stale")
            );
            assert_eq!(io.latest_sample_at, before);
            assert_eq!(
                io.joint_feedback[index(id)].as_ref().unwrap().at,
                joint_time
            );
            let diag = io.feetech_diagnostics().unwrap();
            assert_eq!(diag.sync.missing_ids, vec![id]);
            assert_eq!(diag.telemetry.missing_by_id[&id], 1);
            assert_eq!(diag.torque_state_confirmed, Some(true));
            assert!(
                io.set_torque(true).is_err(),
                "missing feedback must not re-arm"
            );
            device.faults.lock().unwrap().missing.clear();
            io.read().unwrap();
            assert!(io.latest_sample_at > before);
        }
        device.faults.lock().unwrap().missing = vec![10, 32, 34];
        let before = io.latest_sample_at;
        for _ in 0..4 {
            assert!(io.read().is_err());
        }
        assert_eq!(io.latest_sample_at, before);
        assert_eq!(
            io.feetech_diagnostics().unwrap().sync.missing_ids,
            vec![10, 32, 34]
        );
        assert!(
            !device
                .writes
                .lock()
                .unwrap()
                .iter()
                .any(|(_, addr, data)| *addr == 40 && data == &vec![0])
        );
        device.faults.lock().unwrap().missing.clear();
        io.read().unwrap();
        assert!(io.held_joint_positions().iter().all(Option::is_none));
        io.set_torque(false).unwrap();
    }

    #[test]
    fn joint_recovery_keeps_real_timestamps_and_has_a_wall_clock_limit() {
        let (bus, device) = emulator(false);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        io.read().unwrap();
        let j = index(24);
        let t = Instant::now() - Duration::from_millis(40);
        io.joint_feedback[j].as_mut().unwrap().at = t;
        io.joint_feedback[j].as_mut().unwrap().velocity = 0.75;
        device.faults.lock().unwrap().missing = vec![24];
        assert!(io.read().is_err());
        assert_eq!(io.joint_feedback[j].as_ref().unwrap().velocity, 0.75);
        assert_eq!(io.joint_feedback[j].as_ref().unwrap().at, t);
        io.joint_feedback[j].as_mut().unwrap().at = Instant::now() - Duration::from_millis(120);
        assert!(io.read().is_err());
        assert!(
            io.held_joint_positions()[j].is_some(),
            "elapsed time must cap a delayed loop"
        );
        // Inspect the recovered native speed without smoothing history. A position
        // jump across missing frames must not be differentiated into a speed spike.
        io.hd1910 = crate::hd1910::State::default();
        let then = Instant::now() - Duration::from_millis(40);
        io.joint_feedback[j].as_mut().unwrap().at = then;
        set_positions(&device, 2100);
        device.regs.lock().unwrap()[24][58..60].copy_from_slice(&0x8008u16.to_le_bytes());
        device.faults.lock().unwrap().missing.clear();
        let recovered = io.read().unwrap();
        let now = io.joint_feedback[j].as_ref().unwrap().at;
        let expected = (-8.0_f64 * 4.39453125).to_radians();
        assert!((recovered.velocities[j] - expected).abs() < 1e-10);
        assert!(now > then);
        assert_eq!(io.joint_missing[j], 0);
        assert!(io.held_joint_positions()[j].is_none());
    }

    #[test]
    fn imu_protocol_faults_and_missing_initial_feedback_stay_strict() {
        let (bus, device) = emulator(false);
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        device.faults.lock().unwrap().missing = vec![32];
        assert!(
            io.read().is_err(),
            "missing initial feedback must never become a usable observation"
        );
        device.faults.lock().unwrap().missing.clear();
        io.read().unwrap();
        for fault in [
            Faults {
                missing: vec![IMU_ID],
                ..Faults::default()
            },
            Faults {
                checksum_id: Some(32),
                ..Faults::default()
            },
            Faults {
                status_id: Some(32),
                ..Faults::default()
            },
            Faults {
                imu_stale: true,
                ..Faults::default()
            },
        ] {
            *device.faults.lock().unwrap() = fault;
            let old = io.latest_sample_at;
            assert!(io.read().is_err());
            assert_eq!(
                io.latest_sample_at, old,
                "invalid transaction must not retimestamp data"
            );
        }
        *device.faults.lock().unwrap() = Faults::default();
        io.read().unwrap();
        device.faults.lock().unwrap().missing = vec![32];
        assert!(
            io.bus.telemetry(&crate::model::JOINT_IDS).is_err(),
            "commissioning API remains strict"
        );
        assert!(
            io.read_sample(false).is_err(),
            "torque-on refresh remains strict"
        );
        device.faults.lock().unwrap().missing = crate::model::JOINT_IDS.to_vec();
        assert!(
            io.read().is_err(),
            "expired IMU plus absent joints is not a fresh observation"
        );
        assert_eq!(io.feetech_diagnostics().unwrap().sync.missing_ids.len(), 15);
    }

    #[test]
    fn restart_preserves_powered_servos_without_writing_until_explicit_init() {
        let (bus, device) = emulator(false);
        for id in crate::model::JOINT_IDS {
            let mut regs = device.regs.lock().unwrap();
            regs[id as usize][40] = 1;
            regs[id as usize][50] = if id == 34 { 10 } else { 5 };
            regs[id as usize][51] = 20;
        }
        let mut io = FeetechIo::from_bus(bus, calibration()).unwrap();
        assert_eq!(io.torque_state_confirmed, Some(true));
        for _ in 0..30 {
            io.read().unwrap();
        }
        io.write(&JointTargets::new([0.; NUM_JOINTS])).unwrap();
        assert!(
            device.writes.lock().unwrap().is_empty(),
            "opening/restarting must be read-only"
        );
        io.set_torque(true).unwrap();
        assert!(
            !device
                .writes
                .lock()
                .unwrap()
                .iter()
                .any(|(_, a, v)| *a == 40 && v[0] == 0)
        );
        assert!(
            !device
                .writes
                .lock()
                .unwrap()
                .iter()
                .any(|(_, a, _)| *a == 50),
            "verified existing gains need no rewrite"
        );
        io.set_torque(false).unwrap();
        assert!(
            device
                .writes
                .lock()
                .unwrap()
                .iter()
                .any(|(_, a, v)| *a == 40 && v[0] == 0)
        );
    }
}
