//! In-memory persistence of the state the machine writes.
//!
//! The sim's random stream is not stored. Loading this snapshot and playing on
//! does not rebuild the plate appearance that was just saved.

use crate::game::{Game, GameError};

#[derive(Debug, Default)]
pub struct MemoryStore {
    snapshot: Option<String>,
}

impl MemoryStore {
    pub fn save(&mut self, game: &Game) -> Result<(), GameError> {
        self.snapshot =
            Some(serde_json::to_string(game).map_err(|err| GameError::Store(err.to_string()))?);
        Ok(())
    }

    pub fn load(&self) -> Result<Game, GameError> {
        let raw = self
            .snapshot
            .as_deref()
            .ok_or_else(|| GameError::Store("nothing saved".into()))?;
        serde_json::from_str(raw).map_err(|err| GameError::Store(err.to_string()))
    }
}
