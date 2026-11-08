//! Layer B. A distribution against true talent, not one box score.
//!
//! Seed `20261004` repeats this check. It is not a box-score seed and `play` does not read it.
//! Each plate appearance is its own draw. Replaying one input is not how a game is rebuilt.
//!
//! Sample: 40_000 plate appearances.
//! Band: batting average within 0.012 of .300.

use baseball_engine::{
    card_batting_average, load_json, outcome_probabilities, Bases, ComputerManager,
    DistributionFixture, Half, PaInput, Park, PlateOutcome, PrePaCalls, Sim, Situation,
    COMPUTER_BUNT_RATE, LEAGUE_BB, LEAGUE_H, LEAGUE_HBP, LEAGUE_HR, LEAGUE_K,
};

const DISTRIBUTION_SEED: u64 = 20_261_004;
const DISTRIBUTION_SAMPLE: usize = 40_000;
const DISTRIBUTION_BAND: f64 = 0.012;

fn fixture() -> DistributionFixture {
    let path = format!("{}/fixtures/distribution.json", env!("CARGO_MANIFEST_DIR"));
    load_json(&path).unwrap()
}

fn input_from(fixture: &DistributionFixture, wrc_plus: f64, weather: Option<String>) -> PaInput {
    PaInput {
        hitter_id: fixture.id.clone(),
        hitter_name: fixture.id.clone(),
        rates: fixture.rates.clone(),
        wrc_plus,
        pitcher_id: "league".into(),
        pitcher_name: "League".into(),
        pitcher: fixture.pitcher.clone(),
        defense: fixture.defense.rating,
        situation: Situation {
            inning: 1,
            half: Half::Top,
            outs: 0,
            bases: Bases::empty(),
            away_score: 0,
            home_score: 0,
            pitcher_fatigue: 0.0,
            pitcher_ceiling: 100.0,
            postseason: false,
        },
        park: fixture.park.clone(),
        weather,
        calls: PrePaCalls::default(),
    }
}

#[test]
fn stub_hitter_rated_300_lands_near_300() {
    let fixture = fixture();
    assert!((fixture.rates.sum() - 1.0).abs() < 1e-6);
    assert!((fixture.pitcher.k - LEAGUE_K).abs() < 1e-12);
    assert!((fixture.pitcher.bb - LEAGUE_BB).abs() < 1e-12);
    assert!((fixture.pitcher.hbp - LEAGUE_HBP).abs() < 1e-12);
    assert!((fixture.pitcher.hr - LEAGUE_HR).abs() < 1e-12);
    assert!((fixture.pitcher.h - LEAGUE_H).abs() < 1e-12);
    assert!((fixture.defense.rating - 0.0).abs() < 1e-12);
    assert!((fixture.park.run_factor - 1.0).abs() < 1e-12);

    let analytic = outcome_probabilities(&fixture.rates, &fixture.pitcher, 0.0, 1.0);
    let card = card_batting_average(&fixture.rates);
    assert!((card - 0.300).abs() < 1e-9, "card batting average {card}");
    assert!(
        (analytic.batting_average() - 0.300).abs() < 1e-9,
        "matched batting average {}",
        analytic.batting_average()
    );

    let input = input_from(&fixture, fixture.wrc_plus, fixture.weather.clone());
    let mut sim = Sim::from_seed(DISTRIBUTION_SEED);
    let mut hits = 0.0;
    let mut at_bats = 0.0;
    for _ in 0..DISTRIBUTION_SAMPLE {
        let result = sim.resolve(&input);
        match result.outcome {
            PlateOutcome::Walk | PlateOutcome::HitByPitch | PlateOutcome::IntentionalWalk => {}
            PlateOutcome::Single
            | PlateOutcome::Double
            | PlateOutcome::Triple
            | PlateOutcome::HomeRun => {
                hits += 1.0;
                at_bats += 1.0;
            }
            PlateOutcome::CaughtStealing => {}
            _ => at_bats += 1.0,
        }
    }
    let average = hits / at_bats;
    let gap = (average - 0.300_f64).abs();
    assert!(
        gap <= DISTRIBUTION_BAND,
        "batting average {average} from {hits} hits and {at_bats} at-bats over {DISTRIBUTION_SAMPLE} plate appearances (seed {DISTRIBUTION_SEED})"
    );
}

#[test]
fn the_same_seed_repeats_the_check_and_is_not_a_game() {
    let fixture = fixture();
    let input = input_from(&fixture, 100.0, None);
    let mut first = Sim::from_seed(DISTRIBUTION_SEED);
    let mut second = Sim::from_seed(DISTRIBUTION_SEED);
    let left = first.resolve(&input);
    let right = second.resolve(&input);
    assert_eq!(left.outcome, right.outcome);
    assert_eq!(left.pitches, right.pitches);
}

#[test]
fn wrc_plus_and_weather_do_not_change_the_draw() {
    let fixture = fixture();
    let weak = input_from(&fixture, 60.0, None);
    let strong = input_from(&fixture, 160.0, Some("wind".into()));
    let mut left = Sim::from_seed(DISTRIBUTION_SEED);
    let mut right = Sim::from_seed(DISTRIBUTION_SEED);
    let a = left.resolve(&weak);
    let b = right.resolve(&strong);
    assert_eq!(a.outcome, b.outcome);
    assert_eq!(a.pitches, b.pitches);
    assert_eq!(a.change, b.change);
}

/// Manager bunt check. Seed `20261005`. Sample 100_000 calls.
/// Band: bunt rate from 0.006 to 0.010. Intentional walks, steals, and hit-and-runs are 0.
#[test]
fn computer_bunt_rate_is_about_0_8_percent_and_intentional_walks_are_zero() {
    let mut manager = ComputerManager::from_seed(20_261_005);
    let sample = 100_000;
    let mut bunts = 0;
    let mut walks = 0;
    let mut steals = 0;
    let mut hit_and_runs = 0;
    for _ in 0..sample {
        let calls = manager.pre_pa_calls();
        bunts += i32::from(calls.bunt);
        walks += i32::from(calls.intentional_walk);
        steals += i32::from(calls.steal);
        hit_and_runs += i32::from(calls.hit_and_run);
    }
    let rate = f64::from(bunts) / f64::from(sample);
    assert_eq!(COMPUTER_BUNT_RATE, 0.008);
    assert!(
        (0.006..0.010).contains(&rate),
        "bunt rate {rate} over {sample} calls"
    );
    assert_eq!(walks, 0);
    assert_eq!(steals, 0);
    assert_eq!(hit_and_runs, 0);
}

#[test]
fn neutral_park_constant_is_one() {
    let park = Park {
        id: "neutral".into(),
        run_factor: 1.0,
    };
    assert!((park.run_factor - 1.0).abs() < 1e-12);
}
