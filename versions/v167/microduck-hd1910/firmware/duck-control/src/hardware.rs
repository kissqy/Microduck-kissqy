//! Exactly one native protocol owns the port. There is no probing/fallback.
use crate::bus::DynamixelIo;
use crate::feetech::FeetechIo;
use crate::io::{ImuStale, JointTargets, Result, RobotIo, Sensors, SlowSensors};

pub enum HardwareIo {
    Dynamixel(DynamixelIo),
    Feetech(FeetechIo),
}
impl HardwareIo {
    fn inner(&self) -> &dyn RobotIo {
        match self {
            Self::Dynamixel(io) => io,
            Self::Feetech(io) => io,
        }
    }
    fn inner_mut(&mut self) -> &mut dyn RobotIo {
        match self {
            Self::Dynamixel(io) => io,
            Self::Feetech(io) => io,
        }
    }
}
impl RobotIo for HardwareIo {
    fn read(&mut self) -> Result<Sensors> {
        self.inner_mut().read()
    }
    fn write(&mut self, targets: &JointTargets) -> Result<()> {
        self.inner_mut().write(targets)
    }
    fn reboot(&mut self, id: u8) -> Result<()> {
        self.inner_mut().reboot(id)
    }
    fn measures_velocity(&self) -> bool {
        self.inner().measures_velocity()
    }
    fn measures_load(&self) -> bool {
        self.inner().measures_load()
    }
    fn held_joint_positions(&self) -> [Option<f64>; crate::model::NUM_JOINTS] {
        self.inner().held_joint_positions()
    }
    fn set_gain(&mut self, kp: u16) -> Result<()> {
        self.inner_mut().set_gain(kp)
    }
    fn set_torque(&mut self, on: bool) -> Result<()> {
        self.inner_mut().set_torque(on)
    }
    fn slow_sensors(&mut self) -> Result<SlowSensors> {
        self.inner_mut().slow_sensors()
    }
    fn imu_stale(&self) -> ImuStale {
        self.inner().imu_stale()
    }
    fn feetech_diagnostics(&self) -> Option<crate::feetech::FeetechDiagnostics> {
        self.inner().feetech_diagnostics()
    }
    fn feetech_control_status(&self) -> Option<crate::feetech::FeetechControlStatus> {
        self.inner().feetech_control_status()
    }
    fn feetech_snapshot(&self) -> Option<crate::feetech_snapshot::Snapshot> {
        self.inner().feetech_snapshot()
    }
    fn feetech_sync_trace(&self) -> Option<&crate::feetech::SyncTrace> {
        self.inner().feetech_sync_trace()
    }
    fn imu_ready(&self) -> bool {
        self.inner().imu_ready()
    }
}
