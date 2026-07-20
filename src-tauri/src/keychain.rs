//! BYOK API key storage in the OS-native credential store (Windows
//! Credential Manager, macOS Keychain, or the Linux Secret Service),
//! via the `keyring` crate. Keys never touch our SQLite database or a
//! plaintext config file.
//!
//! On successful storage/startup, keys are also pushed to the FastAPI
//! sidecar's in-memory `ModelProviderRouter` (see backend/app/routers/
//! provider.py's `PUT /provider/keys/{provider}`) so the process actually
//! using them (LiteLLM) has them — the sidecar itself is stateless with
//! respect to keys and never persists them either.

use keyring::Entry;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State};

use crate::sidecar::SidecarManager;

const KEYCHAIN_SERVICE: &str = "com.poise.app";

/// Providers a key can be stored for. Kept in sync by hand with
/// backend/app/services/provider.py's `SUPPORTED_PROVIDERS`.
const KNOWN_PROVIDERS: &[&str] = &["openai", "anthropic", "google", "groq", "custom"];

#[derive(Debug, thiserror::Error, Serialize)]
pub enum KeychainError {
    #[error("unknown provider: {0}")]
    UnknownProvider(String),
    #[error("keychain error: {0}")]
    Keyring(String),
    #[error("failed to reach sidecar: {0}")]
    Sidecar(String),
}

impl From<keyring::Error> for KeychainError {
    fn from(err: keyring::Error) -> Self {
        KeychainError::Keyring(err.to_string())
    }
}

fn entry_for(provider: &str) -> Result<Entry, KeychainError> {
    if !KNOWN_PROVIDERS.contains(&provider) {
        return Err(KeychainError::UnknownProvider(provider.to_string()));
    }
    Entry::new(KEYCHAIN_SERVICE, provider).map_err(KeychainError::from)
}

/// Stores `key` in the OS keychain, then immediately forwards it to the
/// running sidecar so it's usable right away (not just after a restart).
#[tauri::command]
pub async fn store_api_key(
    app: AppHandle,
    provider: String,
    key: String,
    base_url: Option<String>,
) -> Result<(), KeychainError> {
    let entry = entry_for(&provider)?;
    entry.set_password(&key)?;

    push_key_to_sidecar(&app, &provider, &key, base_url.as_deref()).await
}

/// Removes a key from the OS keychain and tells the sidecar to forget it
/// too (it's only ever held in that process's memory, so this is mostly
/// about the keychain removal — the sidecar copy disappears on its own
/// once the process restarts, but we clear it eagerly for correctness).
#[tauri::command]
pub async fn delete_api_key(app: AppHandle, provider: String) -> Result<(), KeychainError> {
    let entry = entry_for(&provider)?;
    // `delete_credential` errors if there was nothing stored — that's fine,
    // deleting a key that was never set should be a no-op from the caller's
    // point of view.
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => {}
        Err(err) => return Err(KeychainError::from(err)),
    }

    let manager: State<SidecarManager> = app.state();
    let status = manager.snapshot();
    if status.port == 0 {
        return Ok(());
    }

    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/provider/keys/{}", status.port, provider);
    client
        .delete(url)
        .send()
        .await
        .map_err(|e| KeychainError::Sidecar(e.to_string()))?;

    Ok(())
}

/// Returns just whether a key is present for each known provider — never
/// the key value itself. The frontend uses this to render "configured" /
/// "not configured" badges without ever seeing the secret.
#[tauri::command]
pub fn list_configured_providers() -> Result<Vec<String>, KeychainError> {
    let mut configured = Vec::new();
    for provider in KNOWN_PROVIDERS {
        let entry = entry_for(provider)?;
        if entry.get_password().is_ok() {
            configured.push(provider.to_string());
        }
    }
    Ok(configured)
}

/// Called once from `setup()` after the sidecar reports healthy, so a
/// restarted app re-hydrates the sidecar's in-memory keys from the
/// keychain without the user re-entering anything.
pub async fn rehydrate_sidecar_keys(app: &AppHandle) {
    for provider in KNOWN_PROVIDERS {
        let entry = match entry_for(provider) {
            Ok(e) => e,
            Err(_) => continue,
        };
        if let Ok(key) = entry.get_password() {
            if let Err(err) = push_key_to_sidecar(app, provider, &key, None).await {
                tracing::warn!("failed to rehydrate key for {provider}: {err}");
            }
        }
    }
}

async fn push_key_to_sidecar(
    app: &AppHandle,
    provider: &str,
    key: &str,
    base_url: Option<&str>,
) -> Result<(), KeychainError> {
    let manager: State<SidecarManager> = app.state();
    let status = manager.snapshot();
    if status.port == 0 {
        return Err(KeychainError::Sidecar("sidecar port not yet known".into()));
    }

    #[derive(Serialize)]
    struct Body<'a> {
        key: &'a str,
        base_url: Option<&'a str>,
    }

    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/provider/keys/{}", status.port, provider);
    client
        .put(url)
        .json(&Body { key, base_url })
        .send()
        .await
        .map_err(|e| KeychainError::Sidecar(e.to_string()))?;

    Ok(())
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ConfiguredProvider {
    pub provider: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_unknown_providers_before_touching_the_keychain() {
        let result = entry_for("not-a-real-provider");
        assert!(matches!(result, Err(KeychainError::UnknownProvider(_))));
    }

    #[test]
    fn accepts_every_known_provider() {
        for provider in KNOWN_PROVIDERS {
            assert!(entry_for(provider).is_ok());
        }
    }
}
