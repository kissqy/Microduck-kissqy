//! Broken pipes are local I/O errors, never daemon shutdown requests.
pub fn ignore_sigpipe() -> std::io::Result<()> {
    // Process-wide disposition also covers IPC writes and future audio workers.
    // A failed write still returns EPIPE to its existing error handler.
    if unsafe { libc::signal(libc::SIGPIPE, libc::SIG_IGN) } == libc::SIG_ERR {
        return Err(std::io::Error::last_os_error());
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    #[test]
    fn broken_pipe_child() {
        if std::env::var_os("ROBOTD_PIPE_TEST").is_none() {
            return;
        }
        super::ignore_sigpipe().unwrap();
        let mut fds = [0; 2];
        unsafe {
            assert_eq!(libc::pipe(fds.as_mut_ptr()), 0);
            libc::close(fds[0]);
            assert_eq!(libc::write(fds[1], b"x".as_ptr().cast(), 1), -1);
            assert_eq!(
                std::io::Error::last_os_error().raw_os_error(),
                Some(libc::EPIPE)
            );
            libc::close(fds[1]);
            assert_eq!(libc::raise(libc::SIGPIPE), 0);
        }
        // New worker threads must survive too, not only the audio-specific workers.
        std::thread::spawn(|| unsafe {
            assert_eq!(libc::raise(libc::SIGPIPE), 0);
        })
        .join()
        .unwrap();
    }
    #[test]
    fn closed_reader_and_sigpipe_do_not_exit_daemon() {
        let status = std::process::Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "process_safety::tests::broken_pipe_child",
                "--nocapture",
            ])
            .env("ROBOTD_PIPE_TEST", "1")
            .status()
            .unwrap();
        assert!(status.success(), "broken pipe terminated child: {status}");
    }
}
