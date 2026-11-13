//! An operator-requested skill through the existing API; robotd is unchanged.
use duck_ipc_proto as proto;
use serde_json::Value;
use std::{
    io::{BufRead, BufReader, Write},
    os::unix::net::UnixStream,
    path::Path,
    time::{Duration, Instant},
};

const SKILL: &str = "roller_stand";
const BUDGET: Duration = Duration::from_millis(250);

fn health_gate(health: &proto::HealthResult) -> Result<(), &'static str> {
    if !health.healthy
        || health.bus.consecutive_errors != 0
        || health
            .control_loop
            .as_ref()
            .is_none_or(|l| l.last_tick_age_ms > 100)
    {
        return Err("机器人反馈尚未就绪或已过期");
    }
    if health.imu.is_none_or(|imu| !imu.ready || imu.frozen()) {
        return Err("IMU 尚未就绪或数据冻结");
    }
    Ok(())
}

fn state_gate(state: &proto::RobotState) -> Result<(), &'static str> {
    if state.policy != "walk" || state.safety.limp {
        return Err("须先启用滑轮运动；HOME、卸力或其他动作运行中不执行");
    }
    let Some(imu) = state.imu else {
        return Err("没有实际 IMU 姿态");
    };
    let qnorm = imu.quat.iter().map(|x| x * x).sum::<f64>();
    let gnorm = state.safety.gravity.iter().map(|x| x * x).sum::<f64>();
    if !qnorm.is_finite()
        || !(0.8..=1.2).contains(&qnorm)
        || !gnorm.is_finite()
        || !(0.8..=1.2).contains(&gnorm)
        || !imu.gyro.iter().all(|x| x.is_finite())
        || state.t_ns == 0
    {
        return Err("IMU 姿态无效");
    }
    if !state.safety.fallen || state.safety.gravity[2] <= -0.5 {
        return Err("IMU 未确认倒地；直立时不执行滑轮起身");
    }
    // Cross-check the reported quaternion rather than accepting a stale verdict
    // beside an upright attitude. The native verdict supplies its 200 ms debounce.
    let [_, x, y, _] = imu.quat;
    if -1.0 + 2.0 * (x * x + y * y) / qnorm <= -0.5 {
        return Err("IMU 姿态与倒地判断不一致");
    }
    Ok(())
}

struct Client {
    reader: BufReader<UnixStream>,
    next: u64,
    deadline: Instant,
}
impl Client {
    fn read(&mut self) -> Result<Value, String> {
        let remaining = self.deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return Err("读取最新模式和 IMU 超时".into());
        }
        self.reader
            .get_ref()
            .set_read_timeout(Some(remaining))
            .map_err(|e| e.to_string())?;
        let mut line = String::new();
        if self
            .reader
            .read_line(&mut line)
            .map_err(|e| e.to_string())?
            == 0
        {
            return Err("机器人接口已关闭".into());
        }
        serde_json::from_str(&line).map_err(|e| e.to_string())
    }
    fn call(&mut self, call: proto::Call) -> Result<proto::Response, String> {
        let id = proto::Id::Number(self.next);
        self.next += 1;
        let mut line = serde_json::to_vec(&proto::Request::call(id.clone(), &call))
            .map_err(|e| e.to_string())?;
        line.push(b'\n');
        self.reader
            .get_mut()
            .write_all(&line)
            .map_err(|e| e.to_string())?;
        loop {
            let value = self.read()?;
            if value.get("method").and_then(Value::as_str) == Some(proto::method::ROBOT_STATE) {
                continue;
            }
            let response: proto::Response =
                serde_json::from_value(value).map_err(|e| e.to_string())?;
            if response.id.as_ref() != Some(&id) {
                return Err("机器人响应序号不匹配".into());
            }
            if let Some(error) = &response.error {
                return Err(error.message.clone());
            }
            return Ok(response);
        }
    }
    fn mode(&mut self) -> Result<(), String> {
        let mode = self
            .call(proto::Call::RobotMode)?
            .result_as::<proto::ModeResult>()
            .map_err(|e| e.to_string())?;
        if mode.mode != "roller" {
            return Err("仅滑轮模式允许 L3 起身测试".into());
        }
        Ok(())
    }
    fn health(&mut self) -> Result<(), String> {
        let health = self
            .call(proto::Call::RobotHealth)?
            .result_as::<proto::HealthResult>()
            .map_err(|e| e.to_string())?;
        health_gate(&health).map_err(str::to_owned)
    }
    fn state(&mut self) -> Result<proto::RobotState, String> {
        loop {
            let message: proto::Request =
                serde_json::from_value(self.read()?).map_err(|e| e.to_string())?;
            if let Some(state) = message.as_state() {
                return Ok(state);
            }
        }
    }
}

pub fn run(socket: &Path) -> Result<(), String> {
    let stream = UnixStream::connect(socket).map_err(|e| e.to_string())?;
    run_stream(stream)
}

fn run_stream(stream: UnixStream) -> Result<(), String> {
    stream
        .set_write_timeout(Some(BUDGET))
        .map_err(|e| e.to_string())?;
    let mut client = Client {
        reader: BufReader::new(stream),
        next: 1,
        deadline: Instant::now() + BUDGET,
    };
    client.mode()?;
    client.health()?;
    let subscribed = client
        .call(proto::Call::RobotSubscribe(proto::SubscribeParams {
            hz: Some(50),
        }))?
        .result_as::<proto::SubscribeResult>()
        .map_err(|e| e.to_string())?;
    if !subscribed.accepted || !subscribed.skills.iter().any(|s| s == SKILL) {
        return Err("滑轮起身模型没有加载".into());
    }
    let first = client.state()?;
    state_gate(&first).map_err(str::to_owned)?;
    let second = client.state()?;
    state_gate(&second).map_err(str::to_owned)?;
    if second.t_ns <= first.t_ns || second.t_ns - first.t_ns > 100_000_000 {
        return Err("IMU 状态帧没有及时更新".into());
    }
    // Re-read the robot's mode and health immediately before the one-shot,
    // rather than trusting padd's mode cache or a queued command from reconnect.
    client.mode()?;
    client.health()?;
    let latest = client.state()?;
    state_gate(&latest).map_err(str::to_owned)?;
    if latest.t_ns <= second.t_ns || latest.t_ns - second.t_ns > 100_000_000 {
        return Err("最新 IMU 状态不可用".into());
    }
    let result = client
        .call(proto::Call::RobotDo(proto::DoParams {
            skill: SKILL.into(),
        }))?
        .result_as::<proto::IntentResult>()
        .map_err(|e| e.to_string())?;
    if !result.accepted {
        return Err(result
            .reason
            .unwrap_or_else(|| "机器人未接受起身测试".into()));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn state() -> proto::RobotState {
        serde_json::from_value(serde_json::json!({"t":1.0,"t_ns":1_000_000_000u64,
            "move":{"requested":[0,0,0],"applied":[0,0,0]},"head":[0,0,0,0],
            "policy":"walk","safety":{"fallen":true,"limp":false,"gravity":[1,0,0]},
            "loop":{"hz":50.0,"missed":0},"joints":[],"targets":[],
            "imu":{"quat":[0.7071067811865476,0,0.7071067811865476,0],"gyro":[0,0,0]}}))
        .unwrap()
    }
    fn health() -> proto::HealthResult {
        proto::HealthResult {
            healthy: true,
            imu: Some(proto::ImuHealth {
                ready: true,
                ..Default::default()
            }),
            control_loop: Some(proto::LoopHealth {
                target_hz: 50.0,
                achieved_hz: Some(50.0),
                ticks: 50,
                missed: 0,
                last_tick_age_ms: 10,
            }),
            ..Default::default()
        }
    }
    #[test]
    fn fallen_motion_with_valid_imu_passes() {
        assert!(state_gate(&state()).is_ok());
        assert!(health_gate(&health()).is_ok());
    }
    #[test]
    fn standing_or_unconfirmed_fall_is_refused() {
        let mut s = state();
        s.safety.fallen = false;
        assert!(state_gate(&s).is_err());
        s.safety.fallen = true;
        s.safety.gravity = [0.0, 0.0, -1.0];
        assert!(state_gate(&s).is_err());
    }
    #[test]
    fn home_limp_and_other_skills_are_refused() {
        for label in ["held", "home", "ground_pick", "roller_stand", "sitstand"] {
            let mut s = state();
            s.policy = label.into();
            assert!(state_gate(&s).is_err());
        }
        let mut s = state();
        s.safety.limp = true;
        assert!(state_gate(&s).is_err());
    }
    #[test]
    fn missing_invalid_and_upright_imu_are_refused() {
        let mut s = state();
        s.imu = None;
        assert!(state_gate(&s).is_err());
        s = state();
        s.imu.as_mut().unwrap().quat = [0.0; 4];
        assert!(state_gate(&s).is_err());
        s = state();
        s.imu.as_mut().unwrap().quat = [1.0, 0.0, 0.0, 0.0];
        assert!(state_gate(&s).is_err());
        s = state();
        s.safety.gravity = [f64::NAN, 0.0, 0.0];
        assert!(state_gate(&s).is_err());
    }
    #[test]
    fn unhealthy_stale_and_frozen_feedback_are_refused() {
        let mut h = health();
        h.healthy = false;
        assert!(health_gate(&h).is_err());
        h = health();
        h.bus.consecutive_errors = 1;
        assert!(health_gate(&h).is_err());
        h = health();
        h.control_loop.as_mut().unwrap().last_tick_age_ms = 101;
        assert!(health_gate(&h).is_err());
        h = health();
        h.imu.as_mut().unwrap().ready = false;
        assert!(health_gate(&h).is_err());
        h = health();
        h.imu.as_mut().unwrap().consecutive_stale_blocks = 25;
        assert!(health_gate(&h).is_err());
    }
    fn exchange(
        mode: &str,
        fallen: bool,
        missing_skill: bool,
        change_mode: bool,
    ) -> (Result<(), String>, Vec<String>) {
        use std::thread;
        let (client_stream, stream) = UnixStream::pair().unwrap();
        let mode = mode.to_owned();
        let server = thread::spawn(move || {
            stream
                .set_read_timeout(Some(Duration::from_secs(1)))
                .unwrap();
            let mut reader = BufReader::new(stream);
            let mut methods = Vec::new();
            let mut mode_queries = 0;
            loop {
                let mut line = String::new();
                if reader.read_line(&mut line).unwrap_or(0) == 0 {
                    break;
                }
                let req: proto::Request = serde_json::from_str(&line).unwrap();
                methods.push(req.method.clone());
                let result = match req.method.as_str() {
                    proto::method::ROBOT_MODE => {
                        mode_queries += 1;
                        serde_json::json!({"mode":if change_mode && mode_queries>1 {"walk"} else {&mode}})
                    }
                    proto::method::ROBOT_HEALTH => serde_json::to_value(health()).unwrap(),
                    proto::method::ROBOT_SUBSCRIBE => {
                        serde_json::json!({"accepted":true,"skills":if missing_skill {Vec::<&str>::new()} else {vec![SKILL]}})
                    }
                    proto::method::ROBOT_DO => {
                        assert_eq!(req.params.as_ref().unwrap()["skill"], SKILL);
                        serde_json::json!({"accepted":true})
                    }
                    _ => panic!("unexpected call {}", req.method),
                };
                let response = proto::Response::ok(req.id.clone(), &result);
                let mut bytes = serde_json::to_vec(&response).unwrap();
                bytes.push(b'\n');
                reader.get_mut().write_all(&bytes).unwrap();
                if req.method == proto::method::ROBOT_SUBSCRIBE
                    || (req.method == proto::method::ROBOT_HEALTH && mode_queries > 1)
                {
                    let range = if req.method == proto::method::ROBOT_SUBSCRIBE {
                        0..2
                    } else {
                        2..3
                    };
                    for tick in range {
                        let mut s = state();
                        s.safety.fallen = fallen;
                        s.t_ns += tick * 20_000_000;
                        let mut bytes =
                            serde_json::to_vec(&proto::Request::notify_state(&s)).unwrap();
                        bytes.push(b'\n');
                        let _ = reader.get_mut().write_all(&bytes);
                    }
                }
                if req.method == proto::method::ROBOT_DO {
                    break;
                }
            }
            methods
        });
        let result = run_stream(client_stream);
        let methods = server.join().unwrap();
        (result, methods)
    }
    #[test]
    fn native_socket_executes_exactly_one_guarded_skill() {
        let (result, calls) = exchange("roller", true, false, false);
        assert!(result.is_ok(), "{result:?}");
        assert_eq!(
            calls
                .iter()
                .filter(|m| m.as_str() == proto::method::ROBOT_DO)
                .count(),
            1
        );
    }
    #[test]
    fn failed_gates_send_no_motion_or_skill_request() {
        for (mode, fallen, missing, changed) in [
            ("walk", true, false, false),
            ("roller", false, false, false),
            ("roller", true, true, false),
            ("roller", true, false, true),
        ] {
            let (result, calls) = exchange(mode, fallen, missing, changed);
            assert!(result.is_err());
            assert!(calls.iter().all(|m| m.as_str() != proto::method::ROBOT_DO
                && m.as_str() != proto::method::ROBOT_ENABLE));
        }
    }
}
