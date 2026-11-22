// ABOUTME: Sizes what platoon splits on both cards do to scoring when log5 combines them against one league line.
// ABOUTME: Whole games with 2025 MLB handedness lines, played the site's way and against the handedness-correct environment.

//! The site writes the batter's split against the pitcher's hand onto the batter's card, and the
//! pitcher's split against the batter's side onto the pitcher's card, then the engine combines
//! the two against the overall league line. Each split already carries the platoon edge, so the
//! edge is counted twice.
//!
//! The 2025 fixture holds the four handedness matchup lines. An average left-handed batter's line
//! against right-handers is the LvR cell, and so is an average right-hander's line against
//! left-handed batters, because both are the same plate appearances.
//!
//! Each check plays the same games two ways:
//! - true: the batter carries the matchup cell and the pitcher carries the league line, so
//!   log5 hands back the cell exactly. That is the 2025 handedness environment.
//! - site: both cards carry the matchup cell, which is what the site sends.
//!
//! Seed `20261122`. 10_000 games per environment.

use baseball_engine::runner::step_plate_appearance;
use baseball_engine::{
    load_json, BattedBallRates, BatterCard, ComputerManager, DefenseRating, FatigueProfile, Game,
    GameFixture, Governance, HitterRates, Park, PitcherCard, PitcherRates, PitcherRole, Position,
    Running, Sim, TeamFixture, LEAGUE_BB, LEAGUE_H, LEAGUE_HBP, LEAGUE_HR, LEAGUE_K,
};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde::Deserialize;
use std::collections::BTreeMap;

const PLATOON_SEED: u64 = 20_261_122;
const PLATOON_GAMES: u64 = 10_000;

/// Share of 2025 plate appearances against a right-handed pitcher (LvR + RvR).
const RHP_SHARE: f64 = 0.728;

#[derive(Debug, Deserialize)]
struct Cell {
    k: f64,
    bb: f64,
    hbp: f64,
    single: f64,
    double: f64,
    triple: f64,
    hr: f64,
}

#[derive(Debug, Deserialize)]
struct PlatoonFixture {
    cells: BTreeMap<String, Cell>,
}

fn fixture() -> PlatoonFixture {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/fixtures/platoon_2025.json");
    load_json(path).expect("platoon fixture")
}

fn hitter_rates(cell: &Cell) -> HitterRates {
    HitterRates {
        k: cell.k,
        bb: cell.bb,
        hbp: cell.hbp,
        single: cell.single,
        double: cell.double,
        triple: cell.triple,
        hr: cell.hr,
        bip_out: 1.0
            - (cell.k + cell.bb + cell.hbp + cell.single + cell.double + cell.triple + cell.hr),
    }
}

fn pitcher_rates(cell: &Cell) -> PitcherRates {
    PitcherRates {
        k: cell.k,
        bb: cell.bb,
        hbp: cell.hbp,
        hr: cell.hr,
        h: cell.single + cell.double + cell.triple,
    }
}

fn league_pitcher_rates() -> PitcherRates {
    PitcherRates {
        k: LEAGUE_K,
        bb: LEAGUE_BB,
        hbp: LEAGUE_HBP,
        hr: LEAGUE_HR,
        h: LEAGUE_H,
    }
}

#[derive(Clone, Copy, PartialEq)]
enum Environment {
    True,
    Site,
}

const LINEUP_POSITIONS: [Position; 9] = [
    Position::Center,
    Position::Shortstop,
    Position::Dh,
    Position::First,
    Position::Right,
    Position::Left,
    Position::Third,
    Position::Catcher,
    Position::Second,
];

/// A batter's or pitcher's hand is the last letter of his id.
fn hand(id: &str) -> char {
    id.chars().last().expect("id has a hand")
}

fn team(id: &str, batter_hands: &[char; 9], pitcher_hand: char) -> TeamFixture {
    let lineup = LINEUP_POSITIONS
        .iter()
        .zip(batter_hands)
        .enumerate()
        .map(|(index, (position, bats))| BatterCard {
            id: format!("{id}-b{index}-{bats}"),
            name: format!("{id} {index}"),
            position: *position,
            defense: DefenseRating {
                rating: 0.0,
                measured_at: *position,
            },
            wrc_plus: 100.0,
            rates: hitter_rates(&Cell {
                k: LEAGUE_K,
                bb: LEAGUE_BB,
                hbp: LEAGUE_HBP,
                single: 0.1425,
                double: 0.0453,
                triple: LEAGUE_H - 0.1425 - 0.0453,
                hr: LEAGUE_HR,
            }),
            batted_balls: BattedBallRates::default(),
        })
        .collect();
    let pitcher = |name: String, role, pitches| PitcherCard {
        id: format!("{name}-{pitcher_hand}"),
        name,
        defense: DefenseRating {
            rating: 0.0,
            measured_at: Position::Pitcher,
        },
        rates: league_pitcher_rates(),
        fatigue: FatigueProfile {
            role,
            age: 28,
            season_pitches_per_appearance: pitches,
            career_pitches_per_appearance: pitches,
            season_appearances: 30,
        },
        batted_balls: BattedBallRates::default(),
    };
    let mut pitchers = vec![pitcher(format!("{id}-sp"), PitcherRole::Starter, 95.0)];
    for index in 0..10 {
        pitchers.push(pitcher(
            format!("{id}-rp{index}"),
            PitcherRole::Reliever,
            25.0,
        ));
    }
    TeamFixture {
        id: id.into(),
        name: id.into(),
        home_park_id: "neutral".into(),
        lineup,
        pitchers,
    }
}

/// Writes this plate appearance's matchup lines onto the batter due up and the fielding staff.
fn write_matchup(game: &mut Game, fixture: &PlatoonFixture, environment: Environment) {
    let batting = game.batting_side();
    let fielding = game.fielding_side();
    let throws = hand(&game.club(fielding).pitchers[0].id);
    let club = game.club(batting);
    let bats = hand(&club.lineup[club.batter_index].id);
    let cell = &fixture.cells[&format!("{bats}v{throws}")];

    let club = game.club_mut(batting);
    let index = club.batter_index;
    club.lineup[index].rates = hitter_rates(cell);
    let pitcher = match environment {
        Environment::True => league_pitcher_rates(),
        Environment::Site => pitcher_rates(cell),
    };
    for card in game.club_mut(fielding).pitchers.iter_mut() {
        card.rates = pitcher.clone();
    }
}

/// Runs per team per game. A side's staff throws with one hand for the whole game; the hand is
/// drawn per game, right-handed RHP_SHARE of the time, unless `throws` fixes it.
fn runs_per_team(batter_hands: &[char; 9], throws: Option<char>, environment: Environment) -> f64 {
    let fixture = fixture();
    let mut hands = StdRng::seed_from_u64(PLATOON_SEED);
    let mut manager = ComputerManager::from_seed(PLATOON_SEED);
    let mut sim = Sim::from_seed(PLATOON_SEED);
    let governance = Governance::new();
    let mut runs = 0u64;
    for game_index in 0..PLATOON_GAMES {
        let mut draw = || {
            throws.unwrap_or_else(|| {
                if hands.gen::<f64>() < RHP_SHARE {
                    'R'
                } else {
                    'L'
                }
            })
        };
        let away_throws = draw();
        let home_throws = draw();
        let game_fixture = GameFixture {
            postseason: false,
            parks: vec![Park {
                id: "neutral".into(),
                run_factor: 1.0,
                ..Park::default()
            }],
            weather: None,
            away: team("away", batter_hands, away_throws),
            home: team("home", batter_hands, home_throws),
        };
        let mut game = Game::start(game_fixture, PLATOON_SEED + game_index).unwrap();
        let mut guard = 0;
        while !game.is_final() {
            guard += 1;
            assert!(guard < 2_000, "game {game_index} did not end");
            write_matchup(&mut game, &fixture, environment);
            step_plate_appearance(
                &mut game,
                &mut sim,
                &mut manager,
                &governance,
                None,
                &Running::default(),
            )
            .unwrap();
        }
        runs += u64::from(game.score.away + game.score.home);
    }
    runs as f64 / (2 * PLATOON_GAMES) as f64
}

/// 2025 lineups were 44 percent left-handed batters (LvL + LvR): four lefties in nine.
const LEAGUE_MIX: [char; 9] = ['L', 'R', 'L', 'R', 'L', 'R', 'L', 'R', 'R'];
const ALL_LEFTIES: [char; 9] = ['L'; 9];

/// Band: with the 2025 mix of hands, the site scores no more than the handedness-correct
/// environment. The double count costs more in same-handed matchups than it adds in opposite-handed
/// ones, so league scoring comes out a little lower, not higher.
#[test]
fn both_platoon_splits_do_not_inflate_league_scoring() {
    let true_runs = runs_per_team(&LEAGUE_MIX, None, Environment::True);
    let site_runs = runs_per_team(&LEAGUE_MIX, None, Environment::Site);
    assert!(
        site_runs <= true_runs,
        "site {site_runs:.3} against true {true_runs:.3} runs per team per game (seed {PLATOON_SEED})"
    );
}

/// The double count widens the platoon edge. Nine left-handed batters score more against a
/// right-handed staff than they should, and less against a left-handed one.
/// Bands: at least 0.15 runs per team more against right-handers; at least 0.15 fewer against left-handers.
#[test]
fn both_platoon_splits_widen_the_edge_for_a_stacked_lineup() {
    let true_vs_rhp = runs_per_team(&ALL_LEFTIES, Some('R'), Environment::True);
    let site_vs_rhp = runs_per_team(&ALL_LEFTIES, Some('R'), Environment::Site);
    let true_vs_lhp = runs_per_team(&ALL_LEFTIES, Some('L'), Environment::True);
    let site_vs_lhp = runs_per_team(&ALL_LEFTIES, Some('L'), Environment::Site);
    assert!(
        site_vs_rhp - true_vs_rhp >= 0.15,
        "nine lefties vs RHP: site {site_vs_rhp:.3} against true {true_vs_rhp:.3} (seed {PLATOON_SEED})"
    );
    assert!(
        true_vs_lhp - site_vs_lhp >= 0.15,
        "nine lefties vs LHP: site {site_vs_lhp:.3} against true {true_vs_lhp:.3} (seed {PLATOON_SEED})"
    );
}
