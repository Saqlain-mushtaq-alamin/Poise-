// This attribute hides the console window on Windows release builds, since
// the app is a GUI desktop app, not a CLI tool.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    poise_lib::run();
}
