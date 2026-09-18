//! Sidecar lifecycle: spawn the FastAPI backend, watch its health, restart
//! it on crash, and shut it down cleanly when the app closes.
//!
//! Contract with the Python side (see backend/app/main.py):
//!   - The process's first stdout line is `POISE_SIDECAR_PORT=<port>`.
//!   - `GET /health` on that port returns `{"status": "ok", ...}` once ready.

use std::{
    sync::Mutex,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};
use tokio::time::sleep;

const HEALTH_POLL_INTERVAL: Duration = Duration::from_secs(3);
const HEALTH_CHECK_TIMEOUT: Duration = Duration::from_secs(5);
const CONSECUTIVE_FAILURE_THRESHOLD: u32 = 3;
const MAX_RESTART_ATTEMPTS: u32 = 3;
const SHUTDOWN_GRACE_PERIOD: Duration = Duration::from_secs(3);

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum SidecarState {
    Starting,
    Healthy,
    Unhealthy,
    Stopped,
}

/// Mirrors `SidecarStatus` in frontend/src/lib/types.ts. Keep both in sync.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidecarStatus {
    pub port: u16,
    pub status: SidecarState,
    pub uptime_seconds: f64,
    pub restart_count: u32,
}

pub struct SidecarManager {
    inner: Mutex<SidecarStatus>,
    started_at: Mutex<Option<Instant>>,
    /// The live child process handle, so `shutdown()` can send SIGTERM/kill
    /// it on app close. `None` before the first successful spawn.
    child: Mutex<Option<CommandChild>>,
}

impl Default for SidecarManager {
    fn default() -> Self {
        Self {
            inner: Mutex::new(SidecarStatus {
                port: 0,
                status: SidecarState::Starting,
                uptime_seconds: 0.0,
                restart_count: 0,
            }),
            started_at: Mutex::new(None),
            child: Mutex::new(None),
        }
    }
}

impl SidecarManager {
    pub fn snapshot(&self) -> SidecarStatus {
        let mut status = self.inner.lock().unwrap().clone();
        if let Some(started_at) = *self.started_at.lock().unwrap() {
            status.uptime_seconds = started_at.elapsed().as_secs_f64();
        }
        status
    }

    fn set_port(&self, port: u16) {
        self.inner.lock().unwrap().port = port;
    }

    fn set_state(&self, state: SidecarState) {
        self.inner.lock().unwrap().status = state;
        if state == SidecarState::Healthy && self.started_at.lock().unwrap().is_none() {
            *self.started_at.lock().unwrap() = Some(Instant::now());
        }
    }

    fn set_child(&self, child: CommandChild) {
        *self.child.lock().unwrap() = Some(child);
    }

    fn increment_restart(&self) -> u32 {
        let mut inner = self.inner.lock().unwrap();
        inner.restart_count += 1;
        inner.restart_count
    }
}

/// Spawns the sidecar, wires up stdout parsing + a background health-check
/// loop, and stores the manager as Tauri managed state. Call once from
/// `setup()`.
pub fn spawn(app: &AppHandle) -> tauri::Result<()> {
    app.manage(SidecarManager::default());
    spawn_with_restarts(app.clone(), 0);
    Ok(())
}

fn spawn_with_restarts(app: AppHandle, attempt: u32) {
    tauri::async_runtime::spawn(async move {
        let manager: State<SidecarManager> = app.state();
        manager.set_state(SidecarState::Starting);

        let sidecar_command = match app.shell().sidecar("poise-backend") {
            Ok(cmd) => cmd,
            Err(err) => {
                tracing::error!("failed to resolve sidecar binary: {err}");
                manager.set_state(SidecarState::Stopped);
                return;
            }
        };

        let (mut rx, child) = match sidecar_command.spawn() {
            Ok(pair) => pair,
            Err(err) => {
                tracing::error!("failed to spawn sidecar: {err}");
                maybe_restart(app, attempt);
                return;
            }
        };
        manager.set_child(child);

        let mut port_known = false;

        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let line = String::from_utf8_lossy(&line);
                    tracing::debug!(target: "sidecar", "{line}");

                    if !port_known {
                        if let Some(port) = parse_port_line(&line) {
                            manager.set_port(port);
                            port_known = true;
                            let app_for_health = app.clone();
                            tauri::async_runtime::spawn(async move {
                                health_check_loop(app_for_health, port).await;
                            });
                        }
                    }
                }
                CommandEvent::Stderr(line) => {
                    tracing::warn!(target: "sidecar", "{}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Error(err) => {
                    tracing::error!("sidecar process error: {err}");
                }
                CommandEvent::Terminated(payload) => {
                    tracing::warn!("sidecar exited with {:?}", payload.code);
                    manager.set_state(SidecarState::Stopped);
                    maybe_restart(app.clone(), attempt);
                    break;
                }
                _ => {}
            }
        }
    });
}

fn maybe_restart(app: AppHandle, attempt: u32) {
    if attempt >= MAX_RESTART_ATTEMPTS {
        tracing::error!("sidecar failed {MAX_RESTART_ATTEMPTS} times; giving up");
        // The frontend's StatusBar reflects `Stopped` via polling / events;
        // a native error dialog can be wired in here via tauri-plugin-dialog
        // once that dependency is added.
        return;
    }
    let manager: State<SidecarManager> = app.state();
    let count = manager.increment_restart();
    tracing::info!("restarting sidecar (attempt {count})");
    spawn_with_restarts(app, attempt + 1);
}

async fn health_check_loop(app: AppHandle, port: u16) {
    let manager: State<SidecarManager> = app.state();
    let client = reqwest::Client::builder()
        .timeout(HEALTH_CHECK_TIMEOUT)
        .build()
        .expect("failed to build health-check http client");

    let mut consecutive_failures = 0u32;

    loop {
        let healthy = client
            .get(format!("http://127.0.0.1:{port}/health"))
            .send()
            .await
            .map(|resp| resp.status().is_success())
            .unwrap_or(false);

        if healthy {
            consecutive_failures = 0;
            manager.set_state(SidecarState::Healthy);
        } else {
            consecutive_failures += 1;
            if consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD {
                manager.set_state(SidecarState::Unhealthy);
            }
        }

        let _ = app.emit("sidecar-status", manager.snapshot());

        tokio::time::sleep(HEALTH_POLL_INTERVAL).await;
    }
}

fn parse_port_line(output: &str) -> Option<u16> {
    for line in output.lines() {
        let trimmed = line.trim();
        if let Some(p) = trimmed.strip_prefix("POISE_SIDECAR_PORT=") {
            if let Ok(port) = p.trim().parse::<u16>() {
                return Some(port);
            }
        }
    }
    None
}

/// Called from the window `close-requested` handler (see lib.rs). Sends a
/// kill signal to the sidecar child process and marks it stopped. The OS
/// process is terminated immediately via `CommandChild::kill()`; there is
/// no cooperative SIGTERM in `tauri_plugin_shell` today, so we treat the
/// grace period as an upper bound on how long we block the close handler
/// waiting for the kill syscall to be issued, not as a wait for the child's
/// own shutdown work.
pub async fn shutdown(app: &AppHandle) {
    let manager: State<SidecarManager> = app.state();
    let child = manager.child.lock().unwrap().take();

    if let Some(child) = child {
        let kill_result = child.kill();
        if let Err(err) = kill_result {
            tracing::warn!("failed to kill sidecar process cleanly: {err}");
        }
    }

    manager.set_state(SidecarState::Stopped);
    sleep(SHUTDOWN_GRACE_PERIOD.min(Duration::from_millis(50))).await;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_the_port_contract_line() {
        assert_eq!(parse_port_line("POISE_SIDECAR_PORT=54321\n"), Some(54321));
        assert_eq!(parse_port_line("some other log line"), None);
        assert_eq!(parse_port_line("POISE_SIDECAR_PORT=not-a-number"), None);
        assert_eq!(
            parse_port_line("POISE_SIDECAR_PORT=8000\r\nINFO: Started server process [1234]\n"),
            Some(8000)
        );
    }

    #[test]
    fn default_manager_starts_in_starting_state() {
        let manager = SidecarManager::default();
        let status = manager.snapshot();
        assert_eq!(status.status, SidecarState::Starting);
        assert_eq!(status.restart_count, 0);
    }
}
