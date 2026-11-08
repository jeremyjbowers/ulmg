//! Serve the demo page and the play API on 0.0.0.0:41731.

use std::net::SocketAddr;
use std::process::ExitCode;

use baseball_engine::{demo_router, PlayBook};

#[tokio::main]
async fn main() -> ExitCode {
    let app = demo_router(PlayBook::new());
    let addr: SocketAddr = "0.0.0.0:41731".parse().expect("listen address");
    let listener = match tokio::net::TcpListener::bind(addr).await {
        Ok(listener) => listener,
        Err(err) => {
            eprintln!("bind {addr}: {err}");
            return ExitCode::from(1);
        }
    };
    println!("Play API and demo page at http://127.0.0.1:41731");
    if let Err(err) = axum::serve(listener, app).await {
        eprintln!("{err}");
        return ExitCode::from(1);
    }
    ExitCode::SUCCESS
}
