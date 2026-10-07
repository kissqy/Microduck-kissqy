//! Deployment data exported by Training Studio. No motor or service operations.
use crate::model::{DEFAULT_POSITION, JOINT_NAMES, MOUTH_INDEX, NUM_JOINTS};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{path::Path, sync::OnceLock};

#[derive(Clone, Debug)]
pub struct Contract {
    pub task: String,
    pub slot: String,
    pub home: [f64; NUM_JOINTS],
    pub scale: f64,
    pub training_action_scale: f64,
    pub ema_old_weight: f64,
    /// Explicitly unfiltered exports use direct targets for this model only.
    pub target_filter_passthrough: bool,
    /// A separately declared deployment override; never rewrites the training contract.
    pub runtime_execution_profile: Option<RuntimeExecutionProfile>,
    pub body_padding: bool,
    pub head_padding: bool,
    pub firmware_p: u8,
    pub sit_ramp_s: f64,
    pub command_period_s: Option<f64>,
    pub limits: [(f64, f64); 13],
}

/// Uniform runtime tuning explicitly selected for one exported model. It applies to the
/// same Walk network in every posture; there is no inference-phase or IMU classifier.
#[derive(Clone, Debug, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeExecutionProfile {
    pub schema: String,
    pub model_sha256: String,
    pub mode: String,
    pub action_scale: f64,
    pub head_lowpass: f64,
    pub legs_lowpass: f64,
}

impl RuntimeExecutionProfile {
    fn validate(&self, contract: &Contract, digest: &str) -> Result<(), String> {
        if self.schema != "microduck-runtime-execution/v1"
            || self.mode != "uniform"
            || self.model_sha256 != digest
        {
            return Err("runtime execution profile identity or uniform mode mismatch".into());
        }
        if !contract.is_unfiltered_joint_walk()
            || contract.training_action_scale != 1.0
            || contract.ema_old_weight != 0.0
        {
            return Err(
                "uniform runtime profile requires the unfiltered scale-1 VelStand rough contract"
                    .into(),
            );
        }
        if !self.action_scale.is_finite()
            || !(0.1..=2.0).contains(&self.action_scale)
            || !self.head_lowpass.is_finite()
            || !(0.0..=1.0).contains(&self.head_lowpass)
            || self.head_lowpass == 0.0
            || !self.legs_lowpass.is_finite()
            || !(0.0..=1.0).contains(&self.legs_lowpass)
            || self.legs_lowpass == 0.0
        {
            return Err("invalid uniform action scale or target filter coefficients".into());
        }
        Ok(())
    }
}
static HOME: OnceLock<[f64; NUM_JOINTS]> = OnceLock::new();
static FIRMWARE_P: OnceLock<u8> = OnceLock::new();
pub fn home() -> [f64; NUM_JOINTS] {
    HOME.get().copied().unwrap_or(DEFAULT_POSITION)
}
pub fn firmware_p() -> u8 {
    FIRMWARE_P.get().copied().unwrap_or(5)
}
pub fn install(c: &Contract) -> Result<(), String> {
    HOME.set(c.home)
        .map_err(|_| "deployment Home already initialized".to_string())?;
    FIRMWARE_P
        .set(c.firmware_p)
        .map_err(|_| "deployment gains already initialized".to_string())
}
fn number(v: Option<&Value>, name: &str) -> Result<f64, String> {
    v.and_then(Value::as_f64)
        .filter(|x| x.is_finite())
        .ok_or_else(|| format!("missing finite {name}"))
}
pub fn task_slot(task: &str) -> Result<&'static str, String> {
    if task.starts_with("Mjlab-Velocity-")
        || matches!(
            task,
            "Mjlab-VelStand-Flat-MicroDuck" | "Mjlab-VelStand-Rough-Backlash-MicroDuck"
        )
    {
        Ok("walk")
    } else if task.starts_with("Mjlab-SitStand-") {
        Ok("sitstand")
    } else if task.starts_with("Mjlab-StandUp-") {
        Ok("stand")
    } else if task.starts_with("Mjlab-GroundPick-") {
        Ok("ground_pick")
    } else if task.starts_with("Mjlab-Roulade-") {
        Ok("roulade")
    } else {
        Err(format!("task adapter not supported: {task}"))
    }
}
fn read_json(path: &Path) -> Result<Value, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    serde_json::from_slice(&bytes).map_err(|e| format!("{}: {e}", path.display()))
}
impl Contract {
    /// The gait uses the saved walking scale. Recovery retains the official
    /// standing scale; neither path multiplies its training scale a second time.
    pub fn uses_global_action_scale(&self) -> bool {
        matches!(
            self.task.as_str(),
            "Mjlab-Velocity-Rough-Backlash-MicroDuck" | "Mjlab-VelStand-Rough-Backlash-MicroDuck"
        )
    }
    pub fn is_unfiltered_joint_walk(&self) -> bool {
        self.task == "Mjlab-VelStand-Rough-Backlash-MicroDuck"
            && self.slot == "walk"
            && self.target_filter_passthrough
    }
    pub fn clamp_command(&self, mut c: crate::obs::Command, velocity: bool) -> crate::obs::Command {
        if velocity {
            for i in 0..3 {
                c.twist[i] = c.twist[i].clamp(self.limits[i].0, self.limits[i].1);
            }
        }
        for i in 0..4 {
            c.head[i] = c.head[i].clamp(self.limits[i + 3].0, self.limits[i + 3].1);
        }
        c.body.z = c.body.z.clamp(self.limits[9].0, self.limits[9].1);
        c.body.roll = c.body.roll.clamp(self.limits[10].0, self.limits[10].1);
        c.body.pitch = c.body.pitch.clamp(self.limits[11].0, self.limits[11].1);
        c
    }
    pub fn load(path: &Path) -> Result<Self, String> {
        let directory = path.parent().ok_or("model has no directory")?;
        let contract_path = directory.join("deployment-contract.json");
        let json = read_json(&contract_path)?;
        let manifest = read_json(&directory.join("manifest.json"))?;
        let bytes = std::fs::read(path).map_err(|e| e.to_string())?;
        let digest = Sha256::digest(&bytes)
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<String>();
        if manifest["onnx_sha256"].as_str() != Some(&digest) || manifest["task"] != json["task"] {
            return Err("model checksum or task differs from export manifest".into());
        }
        let mut contract =
            Self::parse(&json).map_err(|e| format!("{}: {e}", contract_path.display()))?;
        let runtime_path = directory.join("deployment-runtime.json");
        if runtime_path.exists() {
            let runtime = read_json(&runtime_path)?;
            contract
                .apply_runtime_commands(&runtime, &digest)
                .map_err(|e| format!("{}: {e}", runtime_path.display()))?;
        }
        let execution_path = directory.join("deployment-execution.json");
        if execution_path.exists() {
            // Typed parsing also rejects duplicate fields instead of losing them in Value.
            let bytes = std::fs::read(&execution_path)
                .map_err(|e| format!("{}: {e}", execution_path.display()))?;
            let profile: RuntimeExecutionProfile = serde_json::from_slice(&bytes)
                .map_err(|e| format!("{}: {e}", execution_path.display()))?;
            profile
                .validate(&contract, &digest)
                .map_err(|e| format!("{}: {e}", execution_path.display()))?;
            contract.runtime_execution_profile = Some(profile);
        }
        Ok(contract)
    }
    fn apply_runtime_commands(&mut self, runtime: &Value, digest: &str) -> Result<(), String> {
        if runtime["schema"] != "microduck-runtime-commands/v1"
            || runtime["model_sha256"].as_str() != Some(digest)
        {
            return Err("runtime command ranges belong to another model".into());
        }
        for (name, dimension, offset, padding) in [
            ("head_pose", 4, 3, self.head_padding),
            ("body_pose", 6, 7, self.body_padding),
        ] {
            if let Some(value) = runtime["commands"].get(name) {
                if padding {
                    return Err("runtime command ranges cannot override zero padding".into());
                }
                let rows = value
                    .as_array()
                    .filter(|r| r.len() == dimension)
                    .ok_or("runtime command dimension mismatch")?;
                for (i, row) in rows.iter().enumerate() {
                    let row = row
                        .as_array()
                        .filter(|r| r.len() == 2)
                        .ok_or("runtime command range mismatch")?;
                    let lo = number(row.first(), "runtime lower limit")?;
                    let hi = number(row.get(1), "runtime upper limit")?;
                    if lo > hi {
                        return Err("invalid runtime command range".into());
                    }
                    self.limits[offset + i] = (lo, hi);
                }
            }
        }
        Ok(())
    }
    pub fn parse(v: &Value) -> Result<Self, String> {
        let current_target_contract = matches!(
            v["task"].as_str(),
            Some(
                "Mjlab-Velocity-Rough-Backlash-MicroDuck"
                    | "Mjlab-StandUp-Rough-Backlash-MicroDuck"
                    | "Mjlab-VelStand-Rough-Backlash-MicroDuck"
            )
        ) && v["task_adapter"] == "hd1910-official0151";
        let official_supported = v["task_adapter"] == "hd1910-official0151"
            && matches!(
                v["task"].as_str(),
                Some(
                    "Mjlab-VelStand-Flat-MicroDuck"
                        | "Mjlab-GroundPick-Flat-MicroDuck"
                        | "Mjlab-Roulade-Flat-MicroDuck"
                        | "Mjlab-StandUp-Flat-MicroDuck"
                        | "Mjlab-Velocity-Rough-Backlash-MicroDuck"
                        | "Mjlab-StandUp-Rough-Backlash-MicroDuck"
                        | "Mjlab-VelStand-Rough-Backlash-MicroDuck"
                )
            )
            && v["target_firmware"]["version"] == "0.15.1"
            && v["control_hz"] == 50.0;
        let v2_supported = v["task_adapter"] == "hd1910-v2"
            && matches!(
                v["task"].as_str(),
                Some(
                    "Mjlab-StandUp-Flat-MicroDuck-V2-HD1910"
                        | "Mjlab-Velocity-Flat-MicroDuck-V2-HD1910"
                )
            );
        if v["schema"] != "microduck-deployment-contract/v1"
            || (v["task_adapter"] != "hd1910-v1" && !v2_supported && !official_supported)
            || v["input_dim"] != 61
            || v["output_dim"] != 14
            || v["obs_normalizer"] != "baked_in_onnx"
        {
            return Err(
                "requires an adapted HD1910 contract, normalized ONNX obs[1,61] -> actions[1,14]"
                    .into(),
            );
        }
        let task = v["task"].as_str().ok_or("missing task")?.to_string();
        let slot = task_slot(&task)?.to_string();
        let names: Vec<_> = JOINT_NAMES
            .iter()
            .enumerate()
            .filter(|(i, _)| *i != MOUTH_INDEX)
            .map(|(_, n)| *n)
            .collect();
        if v["onnx_metadata"]["joint_names"].as_str() != Some(&names.join(",")) {
            return Err("policy joint order mismatch".into());
        }
        let mut home = DEFAULT_POSITION;
        let joints = v["model"]["joints"]
            .as_array()
            .ok_or("missing model joints")?;
        for (index, name) in JOINT_NAMES.iter().enumerate() {
            if index == MOUTH_INDEX {
                home[index] = 0.0;
                continue;
            }
            let rows: Vec<_> = joints
                .iter()
                .filter(|j| j["name"].as_str() == Some(name))
                .collect();
            if rows.len() != 1 {
                return Err(format!("missing or duplicate Home joint {name}"));
            }
            home[index] = number(rows[0].get("home_rad"), "joint Home")?;
        }
        let action = &v["actions"]["joint_pos"];
        if action["use_default_offset"] != true
            || action["offset"] != 0.0
            || !action["clip"].is_null()
        {
            return Err("unsupported action offset/clip".into());
        }
        let inference_scale = if official_supported && v["inference_action_scale"].is_null() {
            1.0
        } else {
            number(v["inference_action_scale"].get("value"), "inference scale")?
        };
        let training_scale = number(action.get("scale"), "training scale")?;
        if inference_scale != 1.0
            || (!official_supported && v["inference_action_scale"]["baked_into_onnx"] != false)
        {
            return Err("this profile requires inference scale 1.0, outside ONNX".into());
        }
        // This export trains the existing target filter, with no separate raw-action EMA.
        let ema = if current_target_contract && v["action_ema_old_weight"].is_null() {
            0.0
        } else {
            number(v.get("action_ema_old_weight"), "action EMA")?
        };
        if !(0.0..1.0).contains(&ema) || training_scale <= 0.0 || training_scale > 2.0 {
            return Err("invalid action scale or EMA".into());
        }
        let target_filter_passthrough =
            current_target_contract && v["action_filter"]["enabled"] == false;
        if current_target_contract {
            let filter = &v["action_filter"];
            let required = &v["required_policy_settings"];
            if !filter["enabled"].is_boolean()
                || filter["version"] != 1
                || filter["control_hz"] != 50.0
                || filter["stage"] != "joint_position_target_after_home_and_scale"
                || filter["reset"] != "first_target_passthrough_per_environment"
                || filter["update"] != "once_per_policy_step"
                || filter["previous_action_observation"] != "raw_policy_output"
                || filter["onnx"] != "external_filter_not_baked_into_graph"
                || number(required.get("action_scale"), "global action scale")? != training_scale
                || ema != 0.0
            {
                return Err("unsupported current target-filter mapping".into());
            }
            for (name, alpha) in [
                ("head_lowpass", "head_alpha"),
                ("legs_lowpass", "legs_alpha"),
            ] {
                let value = number(filter.get(alpha), "target filter alpha")?;
                if value <= 0.0
                    || value > 1.0
                    || number(required.get(name), "required target filter")? != value
                    || (target_filter_passthrough && value != 1.0)
                    || (!target_filter_passthrough
                        && number(action.get(alpha), "trained target filter")? != value)
                    || (target_filter_passthrough
                        && !action[alpha].is_null()
                        && number(action.get(alpha), "trained target filter")? != value)
                {
                    return Err("target filter differs from training".into());
                }
            }
        }
        let terms = v["observations"]["terms"]
            .as_object()
            .ok_or("missing observations")?;
        let expected = [
            "base_ang_vel",
            "projected_gravity",
            "joint_pos",
            "joint_vel",
            "actions",
            "command",
            "head_command",
            "body_command",
        ];
        if terms.len() != expected.len() || expected.iter().any(|n| !terms.contains_key(*n)) {
            return Err("unsupported observation terms".into());
        }
        for (name, function) in [
            ("joint_pos", "joint_pos_rel_backlash"),
            ("joint_vel", "joint_vel_rel_backlash"),
        ] {
            if current_target_contract
                && terms[name]["func"]["callable"]
                    .as_str()
                    .is_none_or(|s| !s.ends_with(function))
            {
                return Err("requires encoder-side backlash observations".into());
            }
        }
        for t in terms.values() {
            if !t["clip"].is_null()
                || (!t["scale"].is_null() && t["scale"] != 1.0)
                || t["history_length"].as_u64().unwrap_or(0) != 0
            {
                return Err("unsupported observation scaling/history".into());
            }
        }
        let head = terms["head_command"]["func"]["callable"]
            .as_str()
            .ok_or("missing head observation function")?;
        let head_padding = head.ends_with("zero_command_padding");
        if !head_padding && !head.ends_with("generated_commands") {
            return Err("unsupported head command function".into());
        }
        if head_padding && terms["head_command"]["params"]["dim"] != 4 {
            return Err("requires four head padding slots".into());
        }
        let body = terms["body_command"]["func"]["callable"]
            .as_str()
            .ok_or("missing body observation function")?;
        let body_padding = body.ends_with("zero_command_padding");
        if !body_padding && !body.ends_with("generated_commands") {
            return Err("unsupported body command function".into());
        }
        if body_padding && terms["body_command"]["params"]["dim"] != 6 {
            return Err("requires six body padding slots".into());
        }
        let acts = v["model"]["actuators"]
            .as_array()
            .ok_or("missing BAM actuator")?;
        if acts.len() != 1
            || acts[0]["parameter_file"]["sha256"]
                != "ef2d51adfb1cc0831b9b02ca19aa9176fceecdf725148d084378d7d9a64afceb"
        {
            return Err("unsupported HD1910 BAM parameter file".into());
        }
        let p = number(acts[0].get("kp_fw"), "BAM firmware P")?;
        if p.fract() != 0.0 || !(1.0..=32.0).contains(&p) {
            return Err("invalid BAM firmware P".into());
        }
        let sit_ramp_s = v["commands"]["twist"]["ramp_s"].as_f64().unwrap_or(2.0);
        let mut limits = [(-1.0, 1.0); 13];
        fn range(v: &Value) -> Result<(f64, f64), String> {
            let a = v
                .as_array()
                .filter(|a| a.len() == 2)
                .ok_or("missing command range")?;
            let lo = number(a.first(), "command lower limit")?;
            let hi = number(a.get(1), "command upper limit")?;
            if lo > hi {
                return Err("invalid command range".into());
            }
            Ok((lo, hi))
        }
        if slot == "walk" {
            for (i, key) in ["lin_vel_x", "lin_vel_y", "ang_vel_z"].iter().enumerate() {
                limits[i] = range(&v["commands"]["twist"]["ranges"][*key])?;
            }
        }
        for i in 0..4 {
            limits[3 + i] = if head_padding {
                (0.0, 0.0)
            } else {
                range(&v["commands"]["head_pose"]["ranges"][i])?
            };
        }
        for i in 0..6 {
            limits[7 + i] = if body_padding {
                (0.0, 0.0)
            } else {
                range(&v["commands"]["body_pose"]["ranges"][i])?
            };
        }
        let command_period_s = v["commands"]["twist"]["period"]
            .as_f64()
            .or_else(|| v["commands"]["twist"]["period_s"].as_f64());
        if slot == "ground_pick"
            && (v["commands"]["twist"]["class_type"]["callable"]
                .as_str()
                .is_none_or(|s| !s.ends_with("GroundPickPhaseCommand"))
                || command_period_s.is_none_or(|p| !p.is_finite() || p <= 0.0))
        {
            return Err("ground pick requires a phase command and positive cycle period".into());
        }
        Ok(Self {
            task,
            slot,
            home,
            // This export's trained scale describes policy.action_scale, which
            // the existing controller already reads from the saved UI setting.
            scale: if current_target_contract {
                1.0
            } else {
                training_scale
            },
            training_action_scale: training_scale,
            ema_old_weight: ema,
            target_filter_passthrough,
            runtime_execution_profile: None,
            body_padding,
            head_padding,
            firmware_p: p as u8,
            sit_ramp_s,
            command_period_s,
            limits,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn contract() -> Value {
        serde_json::from_str(include_str!(
            "../../test-data/walk-teacher14000/deployment-contract.json"
        ))
        .unwrap()
    }
    fn joint_contract() -> Contract {
        Contract::parse(
            &serde_json::from_str(include_str!("../../policies/walk/deployment-contract.json"))
                .unwrap(),
        )
        .unwrap()
    }

    #[test]
    fn joint_rough_export_remains_unfiltered_training_data_with_separate_uniform_override() {
        let c = joint_contract();
        assert_eq!(c.slot, "walk");
        assert_eq!(c.training_action_scale, 1.0);
        assert_eq!(c.scale, 1.0);
        assert_eq!(c.ema_old_weight, 0.0);
        assert!(c.target_filter_passthrough);
        assert!(c.runtime_execution_profile.is_none());
        assert_eq!(c.home, Contract::parse(&contract()).unwrap().home);
        let loaded = Contract::load(Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../policies/walk/policy.onnx"
        )))
        .unwrap();
        let p = loaded.runtime_execution_profile.unwrap();
        assert_eq!(p.mode, "uniform");
        assert_eq!(
            (p.action_scale, p.head_lowpass, p.legs_lowpass),
            (0.9, 0.5, 0.7)
        );
        assert_eq!(loaded.home, c.home);
        assert_eq!(
            loaded.target_filter_passthrough,
            c.target_filter_passthrough
        );
    }

    #[test]
    fn uniform_profile_rejects_wrong_model_nonfinite_values_and_hidden_switch_rules() {
        let json: Value = serde_json::from_str(include_str!(
            "../../policies/walk/deployment-execution.json"
        ))
        .unwrap();
        let profile: RuntimeExecutionProfile = serde_json::from_value(json.clone()).unwrap();
        let digest = profile.model_sha256.clone();
        let c = joint_contract();
        profile.validate(&c, &digest).unwrap();
        assert!(profile.validate(&c, "another-model").is_err());
        assert!(
            profile
                .validate(&Contract::parse(&contract()).unwrap(), &digest)
                .is_err()
        );
        for field in ["action_scale", "head_lowpass", "legs_lowpass"] {
            for invalid in [f64::NAN, f64::INFINITY, -0.1, 0.0, 2.1] {
                let mut bad = profile.clone();
                match field {
                    "action_scale" => bad.action_scale = invalid,
                    "head_lowpass" => bad.head_lowpass = invalid,
                    "legs_lowpass" => bad.legs_lowpass = invalid,
                    _ => unreachable!(),
                }
                assert!(bad.validate(&c, &digest).is_err(), "{field}={invalid}");
            }
            let mut boolean = json.clone();
            boolean[field] = serde_json::json!(true);
            assert!(serde_json::from_value::<RuntimeExecutionProfile>(boolean).is_err());
        }
        let mut old = json;
        old["switch"] = serde_json::json!({"enter_tilt_deg": 35.0});
        assert!(serde_json::from_value::<RuntimeExecutionProfile>(old).is_err());
        let duplicate =
            serde_json::to_string(&profile)
                .unwrap()
                .replacen('{', "{\"mode\":\"uniform\",", 1);
        assert!(serde_json::from_str::<RuntimeExecutionProfile>(&duplicate).is_err());
        let mut bad_contract = c;
        bad_contract.training_action_scale = 0.7;
        assert!(profile.validate(&bad_contract, &digest).is_err());
    }
    /// The uploaded unfiltered recovery teacher uses base scale 1.0 and direct
    /// targets, without assigning the gait's global filters or voltage settings.
    #[test]
    fn rough_stand_contract_keeps_teacher_semantics_and_independent_scale() {
        let v: Value = serde_json::from_str(include_str!(
            "../../policies/stand/deployment-contract.json"
        ))
        .unwrap();
        let c = Contract::load(Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../policies/stand/policy.onnx"
        )))
        .unwrap();
        assert_eq!(c.slot, "stand");
        assert_eq!(c.scale, 1.0);
        assert_eq!(c.ema_old_weight, 0.0);
        assert_eq!(c.firmware_p, 5);
        assert!(!c.uses_global_action_scale());
        assert_eq!(v["teacher_only"], true);
        assert_eq!(c.task, "Mjlab-StandUp-Rough-Backlash-MicroDuck");
        assert!(c.target_filter_passthrough);
        let mut bad = v.clone();
        bad["actions"]["joint_pos"]["scale"] = serde_json::json!(0.0);
        assert!(Contract::parse(&bad).is_err());
        let mut bad_filter = v.clone();
        bad_filter["action_filter"]["head_alpha"] = serde_json::json!(0.5);
        bad_filter["required_policy_settings"]["head_lowpass"] = serde_json::json!(0.5);
        assert!(Contract::parse(&bad_filter).is_err());
    }
    #[test]
    fn runtime_curriculum_restores_full_trained_head_commands_without_changing_home() {
        let path = Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../test-data/walk-teacher14000/policy.onnx"
        ));
        let c = Contract::load(path).unwrap();
        let cmd = c.clamp_command(
            crate::obs::Command {
                head: [2.5, -2.5, 2.5, -2.5],
                ..Default::default()
            },
            true,
        );
        assert_eq!(cmd.head, [1.1, -1.1, 1.4, -0.31]);
        assert_eq!(c.home, Contract::parse(&contract()).unwrap().home);
    }
    #[test]
    fn runtime_commands_reject_wrong_model_and_cannot_override_padding() {
        let mut c = Contract::parse(&contract()).unwrap();
        let mut runtime: Value = serde_json::from_str(include_str!(
            "../../test-data/walk-teacher14000/deployment-runtime.json"
        ))
        .unwrap();
        assert!(c.apply_runtime_commands(&runtime, "wrong model").is_err());
        let digest = runtime["model_sha256"].as_str().unwrap().to_string();
        runtime["commands"]["head_pose"][0][0] = serde_json::json!(2.0);
        assert!(c.apply_runtime_commands(&runtime, &digest).is_err());
        let mut c = Contract::parse(&contract()).unwrap();
        c.head_padding = true;
        runtime["commands"]["head_pose"][0][0] = serde_json::json!(-1.1);
        assert!(c.apply_runtime_commands(&runtime, &digest).is_err());
    }
    #[test]
    fn current_walk_uses_exact_home_and_body_commands() {
        let c = Contract::parse(&contract()).unwrap();
        assert_eq!(c.home[2], -0.4579);
        assert_eq!(c.home[4], 0.453);
        assert_eq!(c.firmware_p, 5);
        assert_eq!(c.ema_old_weight, 0.0);
        assert!(!c.body_padding);
        assert_eq!(c.task, "Mjlab-Velocity-Rough-Backlash-MicroDuck");
        assert_eq!(c.scale, 1.0, "official global scaling is applied only once");
    }

    #[test]
    fn corrected_contract_does_not_require_voltage_adaptation_off() {
        let mut v = contract();
        assert_eq!(v["export_contract_revision"], 2);
        assert!(v["required_policy_settings"]["voltage_adapt"].is_null());
        assert_eq!(
            v["runtime_only_settings"]["voltage_adapt"]["export_behavior"],
            "inherit_existing_runtime_configuration"
        );
        let corrected = Contract::parse(&v).unwrap();
        // The old exporter field is metadata, not a runtime switch.
        v["required_policy_settings"]["voltage_adapt"] = Value::Bool(false);
        let legacy = Contract::parse(&v).unwrap();
        assert_eq!(legacy.home, corrected.home);
        assert_eq!(legacy.scale, corrected.scale);
    }

    #[test]
    fn official0151_adapter_requires_matching_task_and_runtime() {
        let mut v: Value = serde_json::from_str(include_str!(
            "../../policies/ground_pick/deployment-contract.json"
        ))
        .unwrap();
        v["task"] = serde_json::json!("Mjlab-VelStand-Flat-MicroDuck");
        let c = Contract::parse(&v).unwrap();
        assert_eq!(c.slot, "walk");
        assert_eq!(c.scale, 1.0);
        let mut wrong = v.clone();
        wrong["target_firmware"]["version"] = serde_json::json!("0.14.0");
        assert!(Contract::parse(&wrong).is_err());
        let mut wrong = v.clone();
        wrong["task"] = serde_json::json!("Mjlab-StandUp-Flat-MicroDuck-V2-HD1910");
        assert!(Contract::parse(&wrong).is_err());
        let mut scaled = v;
        scaled["inference_action_scale"]["value"] = serde_json::json!(0.7);
        assert!(Contract::parse(&scaled).is_err());
    }
    #[test]
    fn unsupported_joint_order_and_offsets_are_rejected() {
        let mut v = contract();
        v["onnx_metadata"]["joint_names"] = Value::String("wrong".into());
        assert!(Contract::parse(&v).is_err());
        let mut v = contract();
        v["actions"]["joint_pos"]["use_default_offset"] = Value::Bool(false);
        assert!(Contract::parse(&v).is_err());
    }
    #[test]
    fn pick_contract_uses_phase_period_and_zero_head_body_commands() {
        let mut v: Value = serde_json::from_str(include_str!(
            "../../policies/sitstand/deployment-contract.json"
        ))
        .unwrap();
        v["task"] = serde_json::json!("Mjlab-GroundPick-Flat-MicroDuck");
        v["task_adapter"] = serde_json::json!("hd1910-v1");
        v["commands"]["twist"]["class_type"] =
            serde_json::json!({"callable":"GroundPickPhaseCommand"});
        v["commands"]["twist"]["period"] = serde_json::json!(4.0);
        for (term, dim) in [("head_command", 4), ("body_command", 6)] {
            v["observations"]["terms"][term]["func"]["callable"] =
                serde_json::json!("zero_command_padding");
            v["observations"]["terms"][term]["params"]["dim"] = serde_json::json!(dim);
        }
        let c = Contract::parse(&v).unwrap();
        assert_eq!(c.slot, "ground_pick");
        assert_eq!(c.command_period_s, Some(4.0));
        assert!(c.body_padding);
        let command = c.clamp_command(
            crate::obs::Command {
                head: [1.0; 4],
                body: crate::obs::BodyPose {
                    z: 1.0,
                    roll: 1.0,
                    pitch: 1.0,
                },
                ..Default::default()
            },
            false,
        );
        assert_eq!(command.head, [0.0; 4]);
        assert_eq!(command.body, crate::obs::BodyPose::default());
    }

    #[test]
    fn official_ground_pick_export_loads_with_original_hash_and_phase() {
        let path = Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../policies/ground_pick/policy.onnx"
        ));
        let c = Contract::load(path).unwrap();
        assert_eq!(c.slot, "ground_pick");
        assert_eq!(c.command_period_s, Some(4.0));
        assert_eq!(c.firmware_p, 5);
        assert_eq!(c.scale, 1.0);
        assert_eq!(c.ema_old_weight, 0.0);
        assert!(c.head_padding && c.body_padding);
        let walk = Contract::parse(&contract()).unwrap();
        assert_eq!(c.home, walk.home);
    }
}
