//! Slow facts for a connected R17 observer. Never called by the control thread.
//!
//! This replaces the remote Python collector's /proc/sysfs reads; it does not
//! start a monitor, open input devices, subscribe to padd, or change hardware.
use serde_json::{Map, Value, json};
use std::fs::{self, File};
use std::io::{Read, Result as IoResult};
use std::path::Path;
#[cfg(test)]
use std::path::PathBuf;
use std::sync::{LazyLock, Mutex};
use std::time::{Duration, Instant, SystemTime};

const WEBPAD_NAME: &str = "Microduck R17 Web Xbox";

#[derive(Default)]
struct Reader {
    previous_cpu: Option<(Instant, u64, u64)>,
}

static READER: LazyLock<Mutex<Reader>> = LazyLock::new(|| Mutex::new(Reader::default()));

/// A raw source record, sampled at most once per two seconds by the stream
/// publisher. Keeping this behind its own mutex never blocks the motor loop.
pub fn snapshot() -> Value {
    READER
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .read(Path::new("/"))
}

fn text(path: &Path, limit: usize) -> IoResult<String> {
    let mut value = String::new();
    File::open(path)?.take(limit as u64 + 1).read_to_string(&mut value)?;
    if value.len() > limit {
        return Err(std::io::Error::new(std::io::ErrorKind::InvalidData, "source exceeds size limit"));
    }
    Ok(value)
}

fn finite_number(value: &str) -> Option<f64> {
    value.parse::<f64>().ok().filter(|n| n.is_finite())
}

fn json_file(path: &Path, limit: usize) -> Option<Value> {
    serde_json::from_str(&text(path, limit).ok()?).ok()
}

fn cpu_counts(line: &str) -> Option<(u64, u64)> {
    let mut words = line.lines().next()?.split_whitespace();
    if words.next()? != "cpu" {
        return None;
    }
    let counts: Vec<u64> = words.take(8).map(str::parse).collect::<Result<_, _>>().ok()?;
    if counts.len() < 5 {
        return None;
    }
    let total = counts.iter().try_fold(0u64, |sum, value| sum.checked_add(*value))?;
    Some((total, counts[3].checked_add(counts[4])?))
}

fn capability_bit(words: &str, bit: usize) -> bool {
    words.split_whitespace().rev().nth(bit / 64)
        .and_then(|word| u64::from_str_radix(word, 16).ok())
        .is_some_and(|word| word & (1u64 << (bit % 64)) != 0)
}

fn real_gamepads(root: &Path) -> IoResult<Vec<Value>> {
    let mut paths = fs::read_dir(root.join("sys/class/input"))?
        .filter_map(Result::ok)
        .filter(|entry| entry.file_name().to_str().is_some_and(|name| {
            name.strip_prefix("event").is_some_and(|id| !id.is_empty() && id.bytes().all(|c| c.is_ascii_digit()))
        }))
        .map(|entry| entry.path())
        .collect::<Vec<_>>();
    paths.sort();
    let mut pads = Vec::new();
    for path in paths.into_iter().take(256) {
        let device = path.join("device");
        let Ok(name) = text(&device.join("name"), 4096) else { continue };
        let name = name.trim();
        if name == WEBPAD_NAME { continue; }
        let Ok(keys) = text(&device.join("capabilities/key"), 4096) else { continue };
        let Ok(axes) = text(&device.join("capabilities/abs"), 4096) else { continue };
        if capability_bit(&keys, 0x130) && capability_bit(&axes, 0) && capability_bit(&axes, 1) {
            pads.push(json!({"name":name,"event":path.file_name().and_then(|s|s.to_str())}));
        }
    }
    Ok(pads)
}

fn pad_settings(root: &Path) -> Result<Value, String> {
    let current = root.join("etc/robot/feetech-ft5/pad-settings.json");
    let legacy = root.join("var/lib/robot/feetech-ft5/r5/pad-settings.json");
    let path = if current.exists() { current } else if legacy.exists() { legacy }
        else { return Ok(json!({"mouth_percent":100.0,"head_rad":2.5})); };
    let settings: Value = serde_json::from_str(&text(&path, 4096).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    let mouth = settings.get("mouth_percent").and_then(Value::as_f64)
        .filter(|n| n.is_finite() && (0.0..=100.0).contains(n));
    let head = settings.get("head_rad").and_then(Value::as_f64)
        .filter(|n| [0.5, 1.0, 2.5].contains(n));
    match (mouth, head) {
        (Some(mouth), Some(head)) => Ok(json!({"mouth_percent":mouth,"head_rad":head})),
        _ => Err("invalid persisted pad settings".into()),
    }
}

impl Reader {
    fn read(&mut self, root: &Path) -> Value {
        let mut data = Map::new();
        for (field, file) in [("hostname", "proc/sys/kernel/hostname"),
                              ("boot_id", "proc/sys/kernel/random/boot_id")] {
            if let Ok(value) = text(&root.join(file), 4096) {
                data.insert(field.into(), json!(value.trim()));
            }
        }
        if let Ok(value) = text(&root.join("proc/uptime"), 4096)
            && let Some(uptime) = value.split_whitespace().next().and_then(finite_number)
        {
            data.insert("uptime_s".into(), json!(uptime));
        }
        if let Ok(value) = text(&root.join("proc/meminfo"), 65_536) {
            for line in value.lines() {
                let Some((key, value)) = line.split_once(':') else { continue };
                let field = match key { "MemTotal" => "memory_total", "MemAvailable" => "memory_available", _ => continue };
                if let Some(bytes) = value.split_whitespace().next()
                    .and_then(|word| word.parse::<u64>().ok()).and_then(|kb| kb.checked_mul(1024))
                {
                    data.insert(field.into(), json!(bytes));
                }
            }
        }
        if let Ok(value) = text(&root.join("proc/stat"), 65_536)
            && let Some((total, idle)) = cpu_counts(&value)
        {
            let now = Instant::now();
            if let Some((at, previous_total, previous_idle)) = self.previous_cpu
                && now.duration_since(at) <= Duration::from_secs(10)
                && total > previous_total && idle >= previous_idle
            {
                let total_delta = total - previous_total;
                let idle_delta = idle - previous_idle;
                if idle_delta <= total_delta {
                    data.insert("cpu_percent".into(), json!(100.0 * (1.0 - idle_delta as f64 / total_delta as f64)));
                }
            }
            self.previous_cpu = Some((now, total, idle));
        }
        if let Ok(value) = text(&root.join("proc/loadavg"), 4096) {
            let load = value.split_whitespace().take(3).map(finite_number).collect::<Option<Vec<_>>>();
            if let Some(load) = load.filter(|v| v.len() == 3) {
                data.insert("load_average".into(), json!(load));
            }
        }
        let temperature = fs::read_dir(root.join("sys/class/thermal")).ok().into_iter()
            .flatten().filter_map(Result::ok)
            .filter(|entry| entry.file_name().to_str().is_some_and(|name| name.starts_with("thermal_zone")))
            .filter_map(|entry| text(&entry.path().join("temp"), 4096).ok())
            .filter_map(|value| finite_number(value.trim()))
            .map(|value| value / 1000.0).reduce(f64::max);
        data.insert("cpu_temp_c".into(), json!(temperature));
        let mut identities = Map::new();
        for service in ["robotd", "tofd", "mediad", "padd", "updaterd", "configd"] {
            if let Some(value) = json_file(&root.join(format!("run/{service}/identity.json")), 65_536) {
                identities.insert(service.into(), value);
            }
        }
        data.insert("identities".into(), Value::Object(identities));
        let camera_path = root.join("run/mediad/camera.json");
        if let Some(camera) = json_file(&camera_path, 262_144).filter(Value::is_object) {
            data.insert("camera".into(), camera);
            if let Ok(modified) = fs::metadata(camera_path).and_then(|meta| meta.modified()) {
                let age = SystemTime::now().duration_since(modified).unwrap_or_default().as_millis();
                data.insert("camera_age_ms".into(), json!(u64::try_from(age).unwrap_or(u64::MAX)));
            }
        }
        match real_gamepads(root) {
            Ok(pads) => { data.insert("real_gamepads".into(), Value::Array(pads)); }
            Err(error) => { data.insert("real_gamepads_error".into(), json!(error.to_string())); }
        }
        match pad_settings(root) {
            Ok(settings) => { data.insert("pad_settings".into(), settings); }
            Err(error) => { data.insert("pad_settings_error".into(), json!(error)); }
        }
        Value::Object(data)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn put(root: &Path, path: &str, value: &str) {
        let path = root.join(path);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, value).unwrap();
    }

    #[test]
    fn slow_sources_keep_units_and_cpu_delta_without_hardware_handles() {
        let temp = tempfile::tempdir().unwrap(); let root = temp.path();
        put(root,"proc/sys/kernel/hostname","duck-test\n");
        put(root,"proc/sys/kernel/random/boot_id","test-boot\n");
        put(root,"proc/uptime","12.5 1.2\n");
        put(root,"proc/meminfo","MemTotal: 2048 kB\nMemAvailable: 1024 kB\n");
        put(root,"proc/stat","cpu 10 0 10 80 0 0 0 0 3 2\ncpu0 0 0 0 0\n");
        put(root,"proc/loadavg","0.25 0.50 1.00 1/100 123\n");
        put(root,"sys/class/thermal/thermal_zone0/temp","85000\n");
        put(root,"run/robotd/identity.json",r#"{"service":"robotd","pid":123}"#);
        put(root,"run/mediad/camera.json",r#"{"fps":30.0,"consumers":0}"#);
        let mut reader = Reader::default(); let first = reader.read(root);
        assert_eq!(first["memory_total"], 2_097_152); assert_eq!(first["cpu_temp_c"],85.0);
        assert_eq!(first["uptime_s"],12.5); assert_eq!(first["hostname"],"duck-test");
        assert!(first.get("cpu_percent").is_none()); assert_eq!(first["camera"]["consumers"],0);
        put(root,"proc/stat","cpu 20 0 10 90 0 0 0 0\n");
        let next = reader.read(root); assert_eq!(next["cpu_percent"],50.0);
        put(root,"proc/stat","cpu 1 0 1 3 0 0 0 0\n");
        assert!(reader.read(root).get("cpu_percent").is_none(),"counter reset is not a busy CPU");
    }

    #[test]
    fn input_discovery_matches_the_existing_bridge_and_excludes_its_web_device() {
        let temp = tempfile::tempdir().unwrap(); let root = temp.path();
        for (id,name,keys,axes) in [(0,"GameSir-Nova 2 Lite","1000000000000 0 0 0 0","3"),
                                   (1,WEBPAD_NAME,"1000000000000 0 0 0 0","3"),
                                   (2,"keyboard","0","3"), (3,"buttons","1000000000000 0 0 0 0","0")] {
            let stem=format!("sys/class/input/event{id}/device");
            put(root,&format!("{stem}/name"),name); put(root,&format!("{stem}/capabilities/key"),keys);
            put(root,&format!("{stem}/capabilities/abs"),axes);
        }
        assert_eq!(real_gamepads(root).unwrap(),vec![json!({"name":"GameSir-Nova 2 Lite","event":"event0"})]);
    }

    #[test]
    fn settings_are_read_without_starting_an_input_service_and_bad_settings_stay_unknown() {
        let temp = tempfile::tempdir().unwrap(); let root = temp.path();
        assert_eq!(pad_settings(root).unwrap(),json!({"mouth_percent":100.0,"head_rad":2.5}));
        put(root,"etc/robot/feetech-ft5/pad-settings.json",r#"{"mouth_percent":65,"head_rad":0.5}"#);
        assert_eq!(pad_settings(root).unwrap(),json!({"mouth_percent":65.0,"head_rad":0.5}));
        put(root,"etc/robot/feetech-ft5/pad-settings.json",r#"{"mouth_percent":true,"head_rad":0.5}"#);
        assert!(pad_settings(root).is_err());
        assert!(Reader::default().read(root).get("pad_settings_error").is_some());
    }

    #[test]
    fn malformed_or_oversized_sources_do_not_become_zero_measurements() {
        let temp = tempfile::tempdir().unwrap(); let root = temp.path();
        put(root,"proc/uptime","NaN 0"); put(root,"sys/class/thermal/thermal_zone0/temp","Infinity");
        put(root,"run/mediad/camera.json","[]");
        let data = Reader::default().read(root);
        assert!(data.get("uptime_s").is_none()); assert!(data["cpu_temp_c"].is_null());
        assert!(data.get("camera").is_none());
        let long:PathBuf=root.join("long"); fs::write(&long,"12345").unwrap();
        assert!(text(&long,4).is_err());
    }
}
