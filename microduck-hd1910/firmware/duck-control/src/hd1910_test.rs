//! Temporary console P/D/torque experiment. No EEPROM writes or model changes.
//! Missing servo-test-parameters.json leaves the original arm path in charge.
use crate::feetech::Bus;
use crate::hd1910::RegisterSnapshot;
use crate::io::{IoError, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Parameters {
    pub kp: u8,
    pub kd: u8,
    pub torque_limit: u16,
}

pub fn load(calibration_path: &Path) -> Result<Option<Parameters>> {
    let path = calibration_path.with_file_name("servo-test-parameters.json");
    let bytes = match std::fs::read(path) {
        Ok(bytes) => bytes,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(IoError::Bus(format!("servo test parameters: {e}"))),
    };
    let parameters: Parameters = serde_json::from_slice(&bytes)
        .map_err(|e| IoError::Bus(format!("servo test parameters: {e}")))?;
    if parameters.torque_limit > 1000 {
        return Err(IoError::Bus("servo test torque limit exceeds 1000".into()));
    }
    Ok(Some(parameters))
}

fn payload(kp: u8, kd: u8, torque_limit: u16) -> Vec<u8> {
    let [lo, hi] = torque_limit.to_le_bytes();
    vec![lo, hi, kp, kd]
}

pub(crate) fn rows(snapshots: &[RegisterSnapshot], parameters: Parameters) -> Vec<(u8, Vec<u8>)> {
    snapshots
        .iter()
        .map(|s| {
            (
                s.id,
                payload(parameters.kp, parameters.kd, parameters.torque_limit),
            )
        })
        .collect()
}

pub(crate) fn original_rows(snapshots: &[RegisterSnapshot]) -> Vec<(u8, Vec<u8>)> {
    snapshots
        .iter()
        .map(|s| {
            (
                s.id,
                payload(
                    s.temporary_pdi[0],
                    s.temporary_pdi[1],
                    s.torque_limit_raw.unwrap(),
                ),
            )
        })
        .collect()
}

pub(crate) fn verify(bus: &mut Bus, rows: &[(u8, Vec<u8>)]) -> Result<()> {
    let ids: Vec<_> = rows.iter().map(|(id, _)| *id).collect();
    let actual = bus.sync_read(48, 4, &ids)?;
    for (id, expected) in rows {
        if actual.get(id) != Some(expected) {
            return Err(IoError::Bus(format!(
                "ID {id}: servo test P/D/torque limit readback mismatch"
            )));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_an_explicit_saved_test_file_activates_the_extension() {
        let name = format!(
            "servo-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let root = std::env::temp_dir().join(name);
        std::fs::create_dir(&root).unwrap();
        let calibration = root.join("hd1910-calibration.toml");
        assert_eq!(load(&calibration).unwrap(), None);
        let path = root.join("servo-test-parameters.json");
        std::fs::write(&path, r#"{"kp":3,"kd":0,"torque_limit":681}"#).unwrap();
        assert_eq!(
            load(&calibration).unwrap(),
            Some(Parameters {
                kp: 3,
                kd: 0,
                torque_limit: 681
            })
        );
        for invalid in [
            r#"{"kp":256,"kd":0,"torque_limit":681}"#,
            r#"{"kp":3,"kd":0,"torque_limit":1001}"#,
            r#"{"kp":3,"kd":0}"#,
        ] {
            std::fs::write(&path, invalid).unwrap();
            assert!(load(&calibration).is_err());
        }
        std::fs::remove_file(&path).unwrap();
        assert_eq!(load(&calibration).unwrap(), None);
        std::fs::remove_dir(root).unwrap();
    }
}
