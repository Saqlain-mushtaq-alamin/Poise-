//! Tauri commands invocable from the frontend via `@tauri-apps/api/core`'s
//! `invoke()`. Keep this to window/process concerns — session data goes
//! through the FastAPI sidecar over HTTP instead (see frontend/src/lib/api.ts).

use tauri::State;

use crate::sidecar::{SidecarManager, SidecarStatus};

#[tauri::command]
pub fn get_sidecar_status(manager: State<SidecarManager>) -> SidecarStatus {
    manager.snapshot()
}
