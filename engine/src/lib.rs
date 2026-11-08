//! One regular-season baseball game.
//!
//! The library is the state machine, the stateless at-bat simulator, and a minimal
//! computer manager. `play` reads a fixture and plays one game. `serve` keeps a
//! game in memory and steps one plate appearance at a time. AWS Lambda,
//! DigitalOcean, and App Engine are later. This crate runs with Cargo.

pub mod fatigue;
pub mod game;
pub mod governance;
pub mod harness;
pub mod http;
pub mod manager;
pub mod model;
pub mod runner;
pub mod session;
pub mod sim;
pub mod store;

pub use fatigue::{base_ceiling, draw_window, effort_per_pitch};
pub use game::{Game, GameError};
pub use governance::Governance;
pub use http::demo_router;
pub use manager::{
    ComputerManager, COMPUTER_BUNT_RATE, COMPUTER_HIT_AND_RUN_RATE, COMPUTER_IBB_RATE,
    COMPUTER_STEAL_RATE,
};
pub use model::*;
pub use runner::play_game;
pub use session::PlayBook;
pub use sim::{
    card_batting_average, outcome_probabilities, OutcomeProbs, Sim, DEFENSE_HIT_DELTA,
    EXTRA_BASE_RATE, LEAGUE_BB, LEAGUE_H, LEAGUE_HBP, LEAGUE_HR, LEAGUE_K,
};
pub use store::MemoryStore;
