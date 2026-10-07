//! Emit independent native FK results for the browser's display/export test.
//! cargo run -p robotd --example raw_geometry_fixture > geometry-fixture.json
#[path = "../src/telemetry_geometry.rs"]
mod telemetry_geometry;

use duck_ipc_proto::JOINT_NAMES;
use kinematics::{Model, Pose, head::HeadFk};
use serde_json::{Value, json};

fn pose(p: Pose) -> Value {
    json!({"pos": p.pos, "quat": p.quat.wxyz()})
}

fn main() {
    let model = Model::alpha();
    let fk = HeadFk::alpha();
    let mut seed = 0x17144144_u64;
    let mut cases = Vec::new();
    for sample in 0..68 {
        let mut names: Vec<&str> = JOINT_NAMES.to_vec();
        if sample == 65 { names.reverse(); }
        if sample == 66 { names.truncate(7); }
        if sample == 67 { names.clear(); }
        let positions: Vec<f64> = names.iter().map(|_| {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            if sample == 0 { 0.0 } else { ((seed >> 32) as f64 / u32::MAX as f64 - 0.5) * 3.0 }
        }).collect();
        let angle = |name: &str| names.iter().position(|n| *n == name)
            .and_then(|i| positions.get(i)).copied().unwrap_or(0.0);
        let angles: Vec<f64> = model.joint_names().map(angle).collect();
        let head = ["neck_pitch", "head_pitch", "head_yaw", "head_roll"].map(angle);
        let mut frames = json!({
            "camera": pose(fk.camera_in_trunk_cv2(head)),
            "tof": pose(fk.tof_in_trunk(head)),
        });
        if let Some(imu) = fk.head_imu_in_trunk(head) { frames["head_imu"] = pose(imu); }
        cases.push(json!({
            "wire_names": names,
            "positions": positions,
            "expected": {"frames": frames,
                "skeleton": model.body_poses(&angles).into_iter().map(pose).collect::<Vec<_>>()},
        }));
    }
    println!("{}", json!({"definition": telemetry_geometry::definition(), "cases": cases}));
}
