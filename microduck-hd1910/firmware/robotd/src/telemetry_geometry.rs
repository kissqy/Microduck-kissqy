//! Static geometry for the raw telemetry consumer. Export the compiled model
//! once, then let the browser reproduce `mapping::{frames_at,skeleton_at}`.
//! No independent copy of the MJCF constants is maintained by the console.

use kinematics::{Model, Pose, head::{SITE_TO_CV2, SENSOR_IN_CV2_Q}};
use serde_json::{Value, json};

fn pose(value: Pose) -> Value {
    json!({"pos": value.pos, "quat": value.quat.wxyz()})
}

fn hinge(value: Option<(usize, [f64; 3])>) -> Value {
    match value {
        Some((index, axis)) => json!({"index": index, "axis": axis}),
        None => Value::Null,
    }
}

pub fn definition() -> Value {
    let model = Model::alpha();
    let bodies: Vec<_> = model.body_names().enumerate().map(|(index, name)| {
        json!({
            "name": name,
            "parent": model.body_parents()[index],
            "rest": pose(model.body_rest_poses()[index]),
            "joint": hinge(model.body_hinges()[index]),
        })
    }).collect();
    let sites: serde_json::Map<String, Value> = ["head_camera", "tof", "head_imu"]
        .into_iter()
        .filter_map(|name| model.site(name).map(|site| {
            let links: Vec<_> = model.site_links(site).map(|(rest, joint)| {
                json!({"rest": pose(rest), "joint": hinge(joint)})
            }).collect();
            (name.to_owned(), json!(links))
        }))
        .collect();
    json!({
        "schema": "r17.kinematics.v1",
        "joint_names": model.joint_names().collect::<Vec<_>>(),
        "head_joints": ["neck_pitch", "head_pitch", "head_yaw", "head_roll"],
        "bodies": bodies,
        "sites": sites,
        "site_to_cv2": SITE_TO_CV2.wxyz(),
        "sensor_in_cv2": SENSOR_IN_CV2_Q.wxyz(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn definition_is_complete_static_geometry_with_valid_topology() {
        let geometry = definition();
        let model = Model::alpha();
        assert_eq!(geometry["joint_names"].as_array().unwrap().len(), model.num_joints());
        let bodies = geometry["bodies"].as_array().unwrap();
        assert_eq!(bodies.len(), model.body_names().count());
        for (i, body) in bodies.iter().enumerate() {
            if let Some(parent) = body["parent"].as_u64() {
                assert!((parent as usize) < i);
            }
            if let Some(joint) = body["joint"].as_object() {
                assert!(joint["index"].as_u64().unwrap() < model.num_joints() as u64);
            }
        }
        for name in ["head_camera", "tof", "head_imu"] {
            assert_eq!(geometry["sites"][name].is_array(), model.site(name).is_some());
        }
        assert_eq!(geometry, definition(), "metadata must not depend on a live angle sample");
    }
}
