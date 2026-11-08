//! One saved game, kept until this process stops.
//!
//! The book is the play API's memory. It is not written to disk. Reading a game
//! does not resolve the next plate appearance. The simulator's random stream stays
//! in the session, so a later plate appearance cannot rebuild the one already saved.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::game::{Game, GameError};
use crate::governance::Governance;
use crate::manager::ComputerManager;
use crate::model::{
    load_json, BatterCard, GameFixture, Half, LineScore, PlayerId, PrePaCalls, Status,
};
use crate::runner::step_plate_appearance;
use crate::sim::Sim;
use crate::store::MemoryStore;

const FIXTURE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/fixtures/game.json");

#[derive(Debug)]
pub enum PlayError {
    Missing,
    Final,
    Failed(String),
}

pub struct PlayBook {
    next_id: u64,
    games: HashMap<String, Session>,
}

struct Session {
    game: Game,
    sim: Sim,
    manager: ComputerManager,
    store: MemoryStore,
    governance: Governance,
}

impl PlayBook {
    pub fn new() -> Self {
        Self {
            next_id: 0,
            games: HashMap::new(),
        }
    }

    /// Open `fixtures/game.json`, save the first state, and wait.
    pub fn open_fixture(&mut self) -> Result<SavedGame, PlayError> {
        let fixture: GameFixture = load_json(FIXTURE).map_err(PlayError::Failed)?;
        let game = Game::start_random(fixture).map_err(|err| PlayError::Failed(err.to_string()))?;
        let mut store = MemoryStore::default();
        store
            .save(&game)
            .map_err(|err| PlayError::Failed(err.to_string()))?;
        self.next_id += 1;
        let id = format!("g{}", self.next_id);
        let saved = view_game(&id, &game);
        self.games.insert(
            id,
            Session {
                game,
                sim: Sim::from_entropy(),
                manager: ComputerManager::from_entropy(),
                store,
                governance: Governance::new(),
            },
        );
        Ok(saved)
    }

    pub fn read(&self, id: &str) -> Result<SavedGame, PlayError> {
        let session = self.games.get(id).ok_or(PlayError::Missing)?;
        Ok(view_game(id, &session.game))
    }

    /// Honor `call` when it is present. Otherwise the computer manager calls the play.
    /// An empty or spent mound is filled inside this same plate appearance.
    pub fn step(&mut self, id: &str, call: Option<PrePaCalls>) -> Result<SavedGame, PlayError> {
        let session = self.games.get_mut(id).ok_or(PlayError::Missing)?;
        match step_plate_appearance(
            &mut session.game,
            &mut session.sim,
            &mut session.manager,
            &mut session.store,
            &session.governance,
            call,
        ) {
            Ok(()) => Ok(view_game(id, &session.game)),
            Err(GameError::GameOver) => Err(PlayError::Final),
            Err(err) => Err(PlayError::Failed(err.to_string())),
        }
    }
}

impl Default for PlayBook {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SavedGame {
    pub id: String,
    pub state: GameView,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameView {
    pub status: Status,
    pub inning: u8,
    pub half: Half,
    pub inning_label: String,
    pub outs: u8,
    pub outs_label: String,
    pub bases: BaseNames,
    pub score: ScoreView,
    pub line_score: LineScore,
    pub last_play: Option<String>,
    pub next_decision: Option<NextDecision>,
    pub plate_appearances: Vec<PlateAppearanceView>,
    pub postseason: bool,
    pub can_step: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BaseNames {
    pub first: Option<String>,
    pub second: Option<String>,
    pub third: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScoreView {
    pub away_name: String,
    pub home_name: String,
    pub away: u32,
    pub home: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NextDecision {
    pub summary: String,
    pub batter_name: String,
    pub pitcher_name: String,
    pub pitcher_entering: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlateAppearanceView {
    pub index: u32,
    pub batter_id: PlayerId,
    pub batter_name: String,
    pub outcome: String,
    pub pitches: u32,
    pub balls: u8,
    pub strikes: u8,
    pub outs_added: u8,
    pub runs_scored: u8,
}

fn view_game(id: &str, game: &Game) -> SavedGame {
    let final_game = game.is_final();
    SavedGame {
        id: id.to_string(),
        state: GameView {
            status: game.status,
            inning: game.inning,
            half: game.half,
            inning_label: format!("{} of the {}", game.half.name(), ordinal(game.inning)),
            outs: game.outs,
            outs_label: outs_label(game.outs),
            bases: BaseNames {
                first: name_on(game, game.bases.first.as_deref()),
                second: name_on(game, game.bases.second.as_deref()),
                third: name_on(game, game.bases.third.as_deref()),
            },
            score: ScoreView {
                away_name: game.away.name.clone(),
                home_name: game.home.name.clone(),
                away: game.score.away,
                home: game.score.home,
            },
            line_score: game.line_score.clone(),
            last_play: game
                .log
                .iter()
                .rev()
                .find(|entry| entry.text.contains(" pitch"))
                .map(|entry| entry.text.clone()),
            next_decision: if final_game {
                None
            } else {
                Some(next_decision(game))
            },
            plate_appearances: game
                .results
                .iter()
                .enumerate()
                .map(|(index, result)| PlateAppearanceView {
                    index: index as u32 + 1,
                    batter_id: result.batter_id.clone(),
                    batter_name: player_name(game, &result.batter_id),
                    outcome: result.outcome.name().to_string(),
                    pitches: result.pitches.len() as u32,
                    balls: result.count.balls,
                    strikes: result.count.strikes,
                    outs_added: result.change.outs_added,
                    runs_scored: result.change.runs_scored,
                })
                .collect(),
            postseason: game.postseason,
            can_step: !final_game,
        },
    }
}

fn next_decision(game: &Game) -> NextDecision {
    let batting = game.club(game.batting_side());
    let batter = &batting.lineup[batting.batter_index];
    let (pitcher_name, entering) = pitcher_for_next(game);
    let situation = format!(
        "{} of the {}. {}.",
        game.half.name(),
        ordinal(game.inning),
        outs_label(game.outs)
    );
    let due = format!("{} is due up for {}", batter.name, batting.name);
    let mound = if entering {
        format!("{pitcher_name} will enter to pitch before this plate appearance")
    } else {
        format!("{pitcher_name} is pitching")
    };
    NextDecision {
        summary: format!("{situation} {due}. {mound}."),
        batter_name: batter.name.clone(),
        pitcher_name,
        pitcher_entering: entering,
    }
}

fn pitcher_for_next(game: &Game) -> (String, bool) {
    let side = game.fielding_side();
    let club = game.club(side);
    if let Some(id) = &club.pitcher_slot {
        if !game.pitcher_is_spent(side, id) {
            return (player_name(game, id), false);
        }
    }
    let next = club
        .pitchers
        .iter()
        .find(|card| club.available.iter().any(|id| id == &card.id));
    match next {
        Some(card) => (card.name.clone(), true),
        None => ("No pitcher".to_string(), true),
    }
}

fn name_on(game: &Game, id: Option<&str>) -> Option<String> {
    id.map(|id| player_name(game, id))
}

fn player_name(game: &Game, id: &str) -> String {
    fn from_club(
        cards: &[BatterCard],
        pitchers: &[crate::model::PitcherCard],
        id: &str,
    ) -> Option<String> {
        cards
            .iter()
            .find(|card| card.id == id)
            .map(|card| card.name.clone())
            .or_else(|| {
                pitchers
                    .iter()
                    .find(|card| card.id == id)
                    .map(|card| card.name.clone())
            })
    }
    from_club(&game.away.lineup, &game.away.pitchers, id)
        .or_else(|| from_club(&game.home.lineup, &game.home.pitchers, id))
        .unwrap_or_else(|| id.to_string())
}

fn outs_label(outs: u8) -> String {
    if outs == 1 {
        "1 out".to_string()
    } else {
        format!("{outs} outs")
    }
}

fn ordinal(inning: u8) -> String {
    let suffix = match inning % 100 {
        11 | 12 | 13 => "th",
        _ => match inning % 10 {
            1 => "st",
            2 => "nd",
            3 => "rd",
            _ => "th",
        },
    };
    format!("{inning}{suffix}")
}
