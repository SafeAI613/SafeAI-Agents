// AI Agents Desktop — Tauri shell.
//
// Responsibilities of the Rust side:
//   1. On startup, spawn the bundled Python core (FastAPI) as a sidecar process.
//   2. Pipe its stdout/stderr to the Tauri log so you can see the server boot.
//   3. Kill the sidecar when the app exits, so no orphan python process is left behind.
//
// The UI talks to the core over HTTP/WS at http://localhost:8000 (same as in dev), so the
// React client needs no Tauri-specific networking — only the base URL differs in dev vs.
// bundled (handled in the client's api layer).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Holds the sidecar child so we can kill it on exit.
struct CoreProcess(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(CoreProcess(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();

            // "agents-core" must match externalBin in tauri.conf.json (sans path/triple).
            let sidecar = app
                .shell()
                .sidecar("agents-core")
                .expect("failed to create sidecar command");

            let (mut rx, child) = sidecar.spawn().expect("failed to spawn core sidecar");

            // Stash the child handle for shutdown.
            app.state::<CoreProcess>()
                .0
                .lock()
                .unwrap()
                .replace(child);

            // Drain the sidecar's output (useful while developing).
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            println!("[core] {}", String::from_utf8_lossy(&bytes));
                        }
                        CommandEvent::Stderr(bytes) => {
                            eprintln!("[core] {}", String::from_utf8_lossy(&bytes));
                        }
                        CommandEvent::Terminated(payload) => {
                            eprintln!("[core] sidecar exited: {:?}", payload);
                        }
                        _ => {}
                    }
                }
            });

            // Keep the handle reachable for commands added later.
            let _ = handle;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Tauri app")
        .run(|app_handle, event| {
            // On any exit path, terminate the sidecar.
            if let RunEvent::Exit = event {
                if let Some(child) = app_handle
                    .state::<CoreProcess>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    let _ = child.kill();
                }
            }
        });
}
