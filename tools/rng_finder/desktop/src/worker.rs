use serde::Deserialize;
use serde_json::Value;
use std::{
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::mpsc::{self, Receiver},
    thread,
};

#[derive(Debug, Clone, Deserialize)]
pub struct Coordinate {
    pub label: String,
    pub xyz: [String; 3],
}
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase")]
pub enum Event {
    Progress {
        stage: String,
    },
    Result {
        plan: String,
        coordinates: Vec<Coordinate>,
        region: Vec<String>,
        index: usize,
        requirements: Vec<String>,
    },
    World {
        path: String,
        seed: String,
    },
    Exported {
        paths: Vec<String>,
    },
    Error {
        message: String,
        field: Option<String>,
    },
    Cancelled,
}

pub struct Worker {
    child: Child,
    pub events: Receiver<Result<Event, String>>,
    completed: bool,
}
impl Worker {
    pub fn start(tool: &Path, request: Value) -> Result<Self, String> {
        let mut command = Command::new("python3");
        command
            .arg(tool.join("desktop_worker.py"))
            .current_dir(tool)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            command.process_group(0);
        }
        let mut child = command
            .spawn()
            .map_err(|e| format!("Could not start Python 3: {e}"))?;
        let output = child.stdout.take().unwrap();
        let errors = child.stderr.take().unwrap();
        let (sender, events) = mpsc::channel();
        let err_sender = sender.clone();
        thread::spawn(move || {
            let mut reader = BufReader::new(errors);
            // Drain stderr so a verbose child cannot stall; only retain the tail.
            let mut tail = Vec::new();
            let mut buffer = [0; 4096];
            while let Ok(n) = reader.read(&mut buffer) {
                if n == 0 {
                    break;
                }
                tail.extend_from_slice(&buffer[..n]);
                if tail.len() > 8192 {
                    tail.drain(..tail.len() - 8192);
                }
            }
            if !tail.is_empty() {
                let _ = err_sender.send(Err(String::from_utf8_lossy(&tail).into_owned()));
            }
        });
        thread::spawn(move || {
            for line in BufReader::new(output).lines() {
                let event = line.map_err(|e| e.to_string()).and_then(|s| {
                    serde_json::from_str(&s).map_err(|e| format!("Invalid worker response: {e}"))
                });
                if sender.send(event).is_err() {
                    break;
                }
            }
        });
        let mut worker = Self {
            child,
            events,
            completed: false,
        };
        let mut input = worker.child.stdin.take().unwrap();
        if let Err(error) = serde_json::to_writer(&mut input, &request)
            .and_then(|_| input.flush().map_err(serde_json::Error::io))
        {
            return Err(format!("Could not send worker request: {error}"));
        }
        Ok(worker)
    }
    pub fn cancel(&mut self) {
        #[cfg(unix)]
        unsafe {
            libc::kill(-(self.child.id() as i32), libc::SIGTERM);
        }
        #[cfg(not(unix))]
        {
            let _ = self.child.kill();
        }
    }
    pub fn force_stop(&mut self) {
        #[cfg(unix)]
        unsafe {
            libc::kill(-(self.child.id() as i32), libc::SIGKILL);
        }
        let _ = self.child.kill();
    }
    pub fn finished(&mut self) -> bool {
        self.completed = self.child.try_wait().ok().flatten().is_some();
        self.completed
    }
}
impl Drop for Worker {
    fn drop(&mut self) {
        // Allow Python finally/rollback handlers to clean interrupted writes first.
        if !self.completed {
            self.cancel();
            for _ in 0..100 {
                if self.finished() {
                    break;
                }
                thread::sleep(std::time::Duration::from_millis(10));
            }
        }
        // Reap descendants too; Linux is the currently supported desktop platform.
        #[cfg(unix)]
        unsafe {
            libc::kill(-(self.child.id() as i32), libc::SIGKILL);
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn tool_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}
