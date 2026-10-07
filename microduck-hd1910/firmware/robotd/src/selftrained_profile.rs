//! Self-trained HD1910 deployment; hardware calibration remains local.
use crate::params::{BusProtocol, Params};
pub fn configure(p: &mut Params, fake: bool) -> Result<(), String> {
    if fake || p.bus.protocol != BusProtocol::Feetech {
        return Ok(());
    }
    if p.bus.port != "/dev/ttyS2" {
        return Err("HD1910 deployment requires HAT /dev/ttyS2".into());
    }
    let paths = p.policy.resolved();
    let c = match duck_control::deployment::Contract::load(&paths.walk) {
        Ok(c) => c,
        Err(reason) if !p.policy.enabled => {
            tracing::warn!(%reason, "diagnostic mode without policy");
            return Ok(());
        }
        Err(reason) => return Err(reason),
    };
    if c.slot != "walk" {
        return Err("walk slot requires a velocity model".into());
    }
    if p.control.hz != 50 {
        return Err("exported HD1910 policies require 50 Hz".into());
    }
    duck_control::deployment::install(&c)?;
    // Exact action transformation is read per policy by the Controller.
    p.policy.gain = c.firmware_p as u16;
    tracing::info!(task=%c.task, firmware_p=c.firmware_p, "self-trained HD1910 models loaded from disk contracts");
    Ok(())
}
