//! CLI requests use robotd's existing socket. They never contend for the UART.
use serde_json::{Value, json};
use std::{path::Path, process::ExitCode, time::Duration};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

pub async fn call(socket: &Path, method: &str, params: Value) -> ExitCode {
    let request = async {
        let stream = tokio::net::UnixStream::connect(socket).await?;
        let (reader, mut writer) = stream.into_split();
        let mut bytes =
            serde_json::to_vec(&json!({"jsonrpc":"2.0","id":1,"method":method,"params":params}))?;
        bytes.push(b'\n');
        writer.write_all(&bytes).await?;
        let line = BufReader::new(reader)
            .lines()
            .next_line()
            .await?
            .ok_or_else(|| std::io::Error::other("service closed socket"))?;
        let reply: Value = serde_json::from_str(&line)?;
        if let Some(error) = reply.get("error") {
            return Err(std::io::Error::other(error.to_string()));
        }
        let result = reply
            .get("result")
            .ok_or_else(|| std::io::Error::other("missing result"))?;
        println!("{}", serde_json::to_string_pretty(result)?);
        if result.get("accepted").and_then(Value::as_bool) == Some(false) {
            return Err(std::io::Error::other("service refused request"));
        }
        Ok::<(), std::io::Error>(())
    };
    match tokio::time::timeout(Duration::from_secs(5), request).await {
        Ok(Ok(())) => ExitCode::SUCCESS,
        other => {
            eprintln!("robotd service request failed: {other:?}");
            ExitCode::FAILURE
        }
    }
}
