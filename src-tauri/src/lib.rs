mod commands;
mod keychain;
mod sidecar;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "poise_lib=info,tauri=warn".into()),
        )
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            commands::get_sidecar_status,
            keychain::store_api_key,
            keychain::delete_api_key,
            keychain::list_configured_providers,
        ])
        .setup(|app| {
            sidecar::spawn(app.handle())?;
            spawn_key_rehydration(app.handle().clone());

            // Grant microphone + camera permissions in WebView2 on Windows.
            // Without this the browser getUserMedia() call raises NotAllowedError
            // even when the user has enabled mic access in Windows Privacy settings.
            #[cfg(target_os = "windows")]
            {
                let main_window = app.get_webview_window("main");
                if let Some(win) = main_window {
                    win.with_webview(|wv| {
                        #[cfg(windows)]
                        {
                            use webview2_com::Microsoft::Web::WebView2::Win32::{
                                ICoreWebView2_13, COREWEBVIEW2_PERMISSION_KIND_MICROPHONE,
                                COREWEBVIEW2_PERMISSION_KIND_CAMERA,
                                COREWEBVIEW2_PERMISSION_STATE_ALLOW,
                            };
                            use windows::core::Interface;
                            unsafe {
                                if let Ok(wv2_13) = wv.controller().CoreWebView2().cast::<ICoreWebView2_13>() {
                                    let _ = wv2_13.SetPermissionState(
                                        COREWEBVIEW2_PERMISSION_KIND_MICROPHONE,
                                        "",
                                        COREWEBVIEW2_PERMISSION_STATE_ALLOW,
                                        None,
                                    );
                                    let _ = wv2_13.SetPermissionState(
                                        COREWEBVIEW2_PERMISSION_KIND_CAMERA,
                                        "",
                                        COREWEBVIEW2_PERMISSION_STATE_ALLOW,
                                        None,
                                    );
                                }
                            }
                        }
                    }).ok();
                }
            }

            Ok(())
        })

        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let app = window.app_handle().clone();
                tauri::async_runtime::block_on(async move {
                    sidecar::shutdown(&app).await;
                });
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running the Poise application");
}


/// Waits for the sidecar's first healthy report, then pushes any keys
/// already sitting in the OS keychain into it — this is what makes BYOK
/// keys "survive app restart" from the user's point of view, since the
/// sidecar itself never persists them.
fn spawn_key_rehydration(app: tauri::AppHandle) {
    use std::time::Duration;

    use crate::sidecar::{SidecarManager, SidecarState};

    tauri::async_runtime::spawn(async move {
        loop {
            let manager: tauri::State<SidecarManager> = app.state();
            let status = manager.snapshot();
            if status.status == SidecarState::Healthy {
                keychain::rehydrate_sidecar_keys(&app).await;
                break;
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
    });
}
