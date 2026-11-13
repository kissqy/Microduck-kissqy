//! Named access to the existing finite expression player. No queue or bus access.
use std::sync::atomic::{AtomicU64, Ordering};

const PHASE: u64 = 7;
const PENDING: u64 = 1;
const PLAYING: u64 = 2;
const COMPLETED: u64 = 3;
const CANCELLED: u64 = 4;
const SILENT: u64 = 1 << 8;
const SERIAL: u64 = 1 << 16;

#[derive(Default)]
pub struct Slot(AtomicU64);

impl Slot {
    // A single CAS publishes the selection, generation and phase together. A cancel
    // cannot leave a new selection attached to an earlier in-flight request.
    pub fn request(&self, index: Option<usize>, silent: bool) -> Option<u64> {
        if index.is_some_and(|i| i >= crate::emotion_cycle::CYCLE.len()) {
            return None;
        }
        let mut old = self.0.load(Ordering::Acquire);
        loop {
            if matches!(old & PHASE, PENDING | PLAYING) {
                return None;
            }
            let next = ((old & !0xffff).wrapping_add(SERIAL) & !0xffff)
                | ((index.map_or(0, |i| i + 1) as u64) << 3)
                | if silent { SILENT } else { 0 }
                | PENDING;
            match self.0.compare_exchange_weak(old, next, Ordering::AcqRel, Ordering::Acquire) {
                Ok(_) => return Some(next >> 16),
                Err(actual) => old = actual,
            }
        }
    }

    pub fn take(&self) -> bool {
        let old = self.0.load(Ordering::Acquire);
        old & PHASE == PENDING
            && self.0.compare_exchange(old, (old & !PHASE) | PLAYING, Ordering::AcqRel, Ordering::Acquire).is_ok()
    }

    pub fn running(&self) -> bool {
        self.0.load(Ordering::Acquire) & PHASE == PLAYING
    }

    pub fn selection(&self) -> (Option<usize>, bool) {
        let value = self.0.load(Ordering::Acquire);
        let index = ((value >> 3) & 31) as usize;
        (index.checked_sub(1), value & SILENT != 0)
    }

    fn end(&self, phase: u64) {
        let mut old = self.0.load(Ordering::Acquire);
        while matches!(old & PHASE, PENDING | PLAYING) {
            match self.0.compare_exchange_weak(old, (old & !PHASE) | phase, Ordering::AcqRel, Ordering::Acquire) {
                Ok(_) => break,
                Err(actual) => old = actual,
            }
        }
    }

    pub fn cancel(&self) { self.end(CANCELLED); }
    pub fn finish(&self) { self.end(COMPLETED); }
    pub fn cancel_request(&self, request_id: u64) -> bool {
        let mut old = self.0.load(Ordering::Acquire);
        while old >> 16 == request_id && matches!(old & PHASE, PENDING | PLAYING) {
            match self.0.compare_exchange_weak(old, (old & !PHASE) | CANCELLED, Ordering::AcqRel, Ordering::Acquire) {
                Ok(_) => return true,
                Err(actual) => old = actual,
            }
        }
        false
    }

    pub fn report(&self) -> serde_json::Value {
        let value = self.0.load(Ordering::Acquire);
        let index = (((value >> 3) & 31) as usize).checked_sub(1);
        serde_json::json!({
            "request_id": value >> 16,
            "phase": match value & PHASE {
                PENDING => "pending", PLAYING => "playing", COMPLETED => "completed",
                CANCELLED => "cancelled", _ => "idle",
            },
            "name": index.and_then(|i| crate::emotion_cycle::CYCLE.get(i).map(|v| v.0)),
            "silent": value & SILENT != 0,
        })
    }
}

pub fn named_skill(skill: &str) -> Option<(usize, bool)> {
    let (name, silent) = if let Some(name) = skill.strip_prefix("emotion_silent_") {
        (name, true)
    } else {
        (skill.strip_prefix("emotion_")?, false)
    };
    crate::emotion_cycle::CYCLE.iter().position(|v| v.0 == name).map(|index| (index, silent))
}

pub fn catalog() -> serde_json::Value {
    let descriptions = [
        ("难过", "失落、伤心，低头表达难过"),
        ("伤心欲绝", "非常难过；会坐下，结束后仍坐着"),
        ("好奇", "发现新东西，歪头好奇地观察"),
        ("思考", "疑惑、思索、犹豫"),
        ("点头", "肯定、同意，正常点头"),
        ("快速点头", "积极认同、连连点头"),
        ("摇头", "否认、拒绝、不同意"),
        ("生气", "不满、恼怒"),
        ("兴奋", "发现喜欢的东西，惊喜、兴奋"),
        ("大笑", "觉得有趣、开心大笑"),
        ("调皮", "开玩笑、调皮地打趣"),
        ("不服气", "倔强、傲娇、不服气"),
        ("不耐烦", "着急、等待得不耐烦"),
    ];
    serde_json::Value::Array(crate::emotion_cycle::CYCLE.iter().zip(descriptions).map(|(&(name, kind), (label, meaning))| {
        serde_json::json!({"name":name,"label":label,"meaning":meaning,
            "skill":format!("emotion_{name}"),"silent":false,
            "silent_skill":format!("emotion_silent_{name}"),
            "sound_tag":crate::expressions::Expression::sound_at_start(kind),
            "seconds":crate::expressions::Expression::duration(kind).as_secs_f64(),
            "requires":"manual_home_and_hold_walk_idle","stays_seated":name=="devastated"})
    }).collect())
}

pub fn head_limits() -> serde_json::Value {
    let model = kinematics::Model::alpha();
    let axes: serde_json::Map<String, serde_json::Value> = ["neck_pitch", "head_pitch", "head_yaw", "head_roll"]
        .into_iter().filter_map(|name| {
            let (min, max) = model.joint_range(model.joint_index(name)?)?;
            Some((name.to_owned(), serde_json::json!({"min":min,"max":max})))
        }).collect();
    serde_json::json!({"source":"kinematics::Model::alpha MJCF", "kind":"model_reference",
        "unit":"rad", "axes":axes,
        "note":"指令目标范围，不代表实机已到位；仍经过现有模型、标定与舵机保护。",
        "directions":{"head_pitch":"负数抬头，正数低头", "head_yaw":"正数向鸭子自身左侧，负数向右侧"}})
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_slot_retains_completion_and_never_queues() {
        let slot = Slot::default();
        let id = slot.request(Some(6), true).unwrap();
        assert!(slot.request(Some(8), true).is_none());
        assert!(slot.take());
        assert_eq!(slot.selection(), (Some(6), true));
        assert!(slot.running() && !slot.take());
        slot.finish();
        assert_eq!(slot.report()["request_id"], id);
        assert_eq!(slot.report()["phase"], "completed");
        slot.cancel(); // Later HOME must not turn a completed request into a cancelled one.
        assert_eq!(slot.report()["phase"], "completed");
        assert_eq!(slot.request(Some(8), true), Some(id + 1));
        assert!(!slot.cancel_request(id));
        assert!(slot.cancel_request(id+1));
        assert!(!slot.take());
        assert_eq!(slot.report()["phase"], "cancelled");
        assert!(slot.request(Some(13), true).is_none());
    }

    #[test]
    fn catalog_and_ranges_come_from_the_native_player_and_model() {
        let catalog = catalog();
        let rows = catalog.as_array().unwrap();
        assert_eq!(rows.len(), 13);
        for (i, row) in rows.iter().enumerate() {
            assert_eq!(named_skill(row["skill"].as_str().unwrap()), Some((i, false)));
            assert_eq!(named_skill(row["silent_skill"].as_str().unwrap()), Some((i, true)));
            assert!(row["sound_tag"].is_string());
            assert!(row["seconds"].as_f64().unwrap() > 0.0);
        }
        assert!(named_skill("emotion_silent_play_dead").is_none());
        let ranges = head_limits();
        let yaw = &ranges["axes"]["head_yaw"];
        assert!(yaw["max"].as_f64().unwrap() > 2.9);
        assert!(ranges["axes"]["head_roll"]["max"].as_f64().unwrap() < 0.5);
    }
}
