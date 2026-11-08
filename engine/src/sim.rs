//! Stateless at-bat simulator.
//!
//! Same inputs do not have to produce the same result. Nothing in here is stored.
//! A bunt or an intentional walk is resolved only when that call is present.

use rand::rngs::StdRng;
use rand::seq::SliceRandom;
use rand::{Rng, SeedableRng};

use crate::model::{
    Base, BaseOutRunChange, BaserunningEvent, Bases, Count, Fielding, HitterRates, PaInput,
    PaResult, Pitch, PitchKind, PitcherRates, PlateOutcome, PlayerId,
};

/// League line used as the odds-ratio baseline, per plate appearance.
/// `h` is hits that are not home runs.
pub const LEAGUE_K: f64 = 0.226;
pub const LEAGUE_BB: f64 = 0.084;
pub const LEAGUE_HBP: f64 = 0.011;
pub const LEAGUE_HR: f64 = 0.031;
pub const LEAGUE_H: f64 = 0.192;

/// Hit probability moved into a ball-in-play out, per point of defense, per plate appearance.
pub const DEFENSE_HIT_DELTA: f64 = 0.002;

/// Chance a runner takes one extra base. There is no speed rating.
pub const EXTRA_BASE_RATE: f64 = 0.25;

pub const BUNT_HIT_RATE: f64 = 0.15;
pub const BUNT_SAC_RATE: f64 = 0.60;
pub const STEAL_SUCCESS_RATE: f64 = 0.75;
pub const HIT_AND_RUN_K_KEEP: f64 = 0.5;

#[derive(Debug, Clone, PartialEq)]
pub struct OutcomeProbs {
    pub k: f64,
    pub bb: f64,
    pub hbp: f64,
    pub single: f64,
    pub double: f64,
    pub triple: f64,
    pub hr: f64,
    pub bip_out: f64,
}

impl OutcomeProbs {
    pub fn sum(&self) -> f64 {
        self.k
            + self.bb
            + self.hbp
            + self.single
            + self.double
            + self.triple
            + self.hr
            + self.bip_out
    }

    pub fn non_hr_hits(&self) -> f64 {
        self.single + self.double + self.triple
    }

    pub fn batting_average(&self) -> f64 {
        let hits = self.non_hr_hits() + self.hr;
        let at_bats = hits + self.k + self.bip_out;
        if at_bats == 0.0 {
            0.0
        } else {
            hits / at_bats
        }
    }
}

pub fn card_batting_average(rates: &HitterRates) -> f64 {
    let hits = rates.hits();
    let at_bats = 1.0 - rates.bb - rates.hbp;
    if at_bats <= 0.0 {
        0.0
    } else {
        hits / at_bats
    }
}

fn odds(rate: f64) -> f64 {
    if rate <= 0.0 {
        return 0.0;
    }
    if rate >= 1.0 {
        return 1.0e12;
    }
    rate / (1.0 - rate)
}

/// Odds-ratio matchup. A pitcher equal to the league line returns the hitter's rate.
pub fn log5(batter: f64, pitcher: f64, league: f64) -> f64 {
    let league_odds = odds(league);
    if league_odds == 0.0 {
        return batter.clamp(0.0, 1.0);
    }
    let combined = odds(batter) * odds(pitcher) / league_odds;
    if !combined.is_finite() {
        return 1.0;
    }
    combined / (1.0 + combined)
}

/// Matchup, park, and defense. wRC+ is not an input. Weather is not an input.
pub fn outcome_probabilities(
    hitter: &HitterRates,
    pitcher: &PitcherRates,
    defense: f64,
    run_factor: f64,
) -> OutcomeProbs {
    let mut k = log5(hitter.k, pitcher.k, LEAGUE_K);
    let mut bb = log5(hitter.bb, pitcher.bb, LEAGUE_BB);
    let mut hbp = log5(hitter.hbp, pitcher.hbp, LEAGUE_HBP);
    let mut hr = log5(hitter.hr, pitcher.hr, LEAGUE_HR);
    let mut hits = log5(hitter.non_hr_hits(), pitcher.h, LEAGUE_H);

    let matched = k + bb + hbp + hr + hits;
    let mut bip = if matched >= 1.0 {
        let scale = 1.0 / matched;
        k *= scale;
        bb *= scale;
        hbp *= scale;
        hr *= scale;
        hits *= scale;
        0.0
    } else {
        1.0 - matched
    };

    // A run factor of 1 leaves the rates where they are, then the renormalize is a no-op.
    hits *= run_factor;
    hr *= run_factor;
    let scaled = k + bb + hbp + hr + hits + bip;
    if scaled > 0.0 {
        let scale = 1.0 / scaled;
        k *= scale;
        bb *= scale;
        hbp *= scale;
        hr *= scale;
        hits *= scale;
        bip *= scale;
    }

    let delta = defense * DEFENSE_HIT_DELTA;
    if delta >= 0.0 {
        let shift = delta.min(hits);
        hits -= shift;
        bip += shift;
    } else {
        let shift = (-delta).min(bip);
        hits += shift;
        bip -= shift;
    }

    let denom = hitter.non_hr_hits();
    let (single_share, double_share, triple_share) = if denom <= 1e-12 {
        (1.0, 0.0, 0.0)
    } else {
        (
            hitter.single / denom,
            hitter.double / denom,
            hitter.triple / denom,
        )
    };

    OutcomeProbs {
        k,
        bb,
        hbp,
        single: hits * single_share,
        double: hits * double_share,
        triple: hits * triple_share,
        hr,
        bip_out: bip,
    }
}

/// Halve the strikeout rate and give that mass to hits and ball-in-play outs.
pub fn apply_hit_and_run(probs: &mut OutcomeProbs) {
    let removed = probs.k * (1.0 - HIT_AND_RUN_K_KEEP);
    probs.k -= removed;
    let contact = probs.non_hr_hits() + probs.bip_out;
    if contact <= 0.0 {
        probs.single += removed;
        return;
    }
    let hit_share = probs.non_hr_hits() / contact;
    let added_hits = removed * hit_share;
    probs.bip_out += removed - added_hits;
    if probs.non_hr_hits() <= 0.0 {
        probs.single += added_hits;
        return;
    }
    let single = probs.single;
    let double = probs.double;
    let triple = probs.triple;
    let denom = single + double + triple;
    probs.single += added_hits * (single / denom);
    probs.double += added_hits * (double / denom);
    probs.triple += added_hits * (triple / denom);
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StealTarget {
    Second,
    Third,
}

pub fn steal_target(bases: &Bases) -> Option<StealTarget> {
    if bases.first.is_some() && bases.second.is_none() {
        Some(StealTarget::Second)
    } else if bases.second.is_some() && bases.third.is_none() {
        Some(StealTarget::Third)
    } else {
        None
    }
}

pub fn apply_steal(bases: &Bases, target: StealTarget, success: bool) -> (Bases, BaserunningEvent) {
    let mut next = bases.clone();
    let (runner, to) = match target {
        StealTarget::Second => (next.first.take(), Base::Second),
        StealTarget::Third => (next.second.take(), Base::Third),
    };
    let runner = runner.unwrap_or_else(|| "runner".to_string());
    if success {
        match to {
            Base::Second => next.second = Some(runner.clone()),
            Base::Third => next.third = Some(runner.clone()),
            Base::First => {}
        }
        (next, BaserunningEvent::StolenBase { runner, to })
    } else {
        (next, BaserunningEvent::CaughtStealing { runner, at: to })
    }
}

#[derive(Debug, Clone, Copy)]
pub struct AdvanceOptions {
    pub take_extra_base: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Advancement {
    pub bases: Bases,
    pub outs_added: u8,
    pub runs_scored: u8,
    pub events: Vec<BaserunningEvent>,
    pub batter_completed: bool,
}

fn score(runner: PlayerId, runs: &mut u8, events: &mut Vec<BaserunningEvent>) {
    *runs += 1;
    events.push(BaserunningEvent::Scored { runner });
}

/// How runners move on a finished batter outcome. Extra-base chances are decided by the caller.
pub fn advance(
    bases: &Bases,
    batter: &str,
    outcome: PlateOutcome,
    outs_before: u8,
    options: AdvanceOptions,
) -> Advancement {
    let first = bases.first.clone();
    let second = bases.second.clone();
    let third = bases.third.clone();
    let mut events = Vec::new();
    let mut runs = 0u8;
    let mut next = Bases::empty();

    let (outs_added, batter_completed) = match outcome {
        PlateOutcome::CaughtStealing => {
            return Advancement {
                bases: bases.clone(),
                outs_added: 1,
                runs_scored: 0,
                events,
                batter_completed: false,
            };
        }
        PlateOutcome::Strikeout | PlateOutcome::BipOut | PlateOutcome::BuntOut => {
            next = bases.clone();
            (1, true)
        }
        PlateOutcome::Walk | PlateOutcome::HitByPitch | PlateOutcome::IntentionalWalk => {
            if first.is_some() {
                if second.is_some() {
                    if let Some(runner) = third.clone() {
                        score(runner, &mut runs, &mut events);
                    }
                    next.third = second.clone();
                }
                next.second = first.clone();
            }
            next.first = Some(batter.to_string());
            (0, true)
        }
        PlateOutcome::Single | PlateOutcome::BuntSingle => {
            if let Some(runner) = third.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = second.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = first.clone() {
                if options.take_extra_base {
                    next.third = Some(runner.clone());
                    events.push(BaserunningEvent::TookExtraBase {
                        runner,
                        to: Base::Third,
                    });
                } else {
                    next.second = Some(runner);
                }
            }
            next.first = Some(batter.to_string());
            (0, true)
        }
        PlateOutcome::Double => {
            if let Some(runner) = third.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = second.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = first.clone() {
                if options.take_extra_base {
                    score(runner, &mut runs, &mut events);
                } else {
                    next.third = Some(runner);
                }
            }
            next.second = Some(batter.to_string());
            (0, true)
        }
        PlateOutcome::Triple => {
            if let Some(runner) = third.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = second.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = first.clone() {
                score(runner, &mut runs, &mut events);
            }
            next.third = Some(batter.to_string());
            (0, true)
        }
        PlateOutcome::HomeRun => {
            if let Some(runner) = third.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = second.clone() {
                score(runner, &mut runs, &mut events);
            }
            if let Some(runner) = first.clone() {
                score(runner, &mut runs, &mut events);
            }
            score(batter.to_string(), &mut runs, &mut events);
            (0, true)
        }
        PlateOutcome::BuntSacrifice => {
            if outs_before >= 2 || !bases.any() {
                next = bases.clone();
            } else {
                if let Some(runner) = third.clone() {
                    score(runner, &mut runs, &mut events);
                }
                next.third = second.clone();
                next.second = first.clone();
            }
            (1, true)
        }
    };

    Advancement {
        bases: next,
        outs_added,
        runs_scored: runs,
        events,
        batter_completed,
    }
}

pub struct Sim {
    rng: StdRng,
}

impl Sim {
    pub fn from_seed(seed: u64) -> Self {
        Self {
            rng: StdRng::seed_from_u64(seed),
        }
    }

    pub fn from_entropy() -> Self {
        Self {
            rng: StdRng::from_entropy(),
        }
    }

    pub fn resolve(&mut self, input: &PaInput) -> PaResult {
        // Received and unused. wRC+ feeds fatigue in the state machine. Weather has no effect.
        // Fatigue is part of the situation and does not change the draw.
        let _unused = (
            input.wrc_plus,
            input.situation.pitcher_fatigue,
            input.situation.pitcher_ceiling,
            input.weather.as_deref(),
            input.situation.postseason,
        );

        let mut bases = input.situation.bases.clone();
        let mut events = Vec::new();
        let mut outs_from_running = 0u8;

        if input.calls.steal && !input.calls.hit_and_run {
            if let Some(target) = steal_target(&bases) {
                let success = self.rng.gen::<f64>() < STEAL_SUCCESS_RATE;
                let (next, event) = apply_steal(&bases, target, success);
                bases = next;
                let caught = !success;
                events.push(event);
                if caught {
                    outs_from_running = 1;
                    if input.situation.outs + outs_from_running >= 3 {
                        return self.package(
                            input,
                            PlateOutcome::CaughtStealing,
                            Advancement {
                                bases,
                                outs_added: outs_from_running,
                                runs_scored: 0,
                                events,
                                batter_completed: false,
                            },
                        );
                    }
                }
            }
        }

        if input.calls.intentional_walk {
            let adv = advance(
                &bases,
                &input.hitter_id,
                PlateOutcome::IntentionalWalk,
                input.situation.outs + outs_from_running,
                AdvanceOptions {
                    take_extra_base: false,
                },
            );
            return self.package(
                input,
                PlateOutcome::IntentionalWalk,
                merge(outs_from_running, events, adv),
            );
        }

        if input.calls.bunt {
            let outcome = self.draw_bunt(&bases, input.situation.outs + outs_from_running);
            let adv = advance(
                &bases,
                &input.hitter_id,
                outcome,
                input.situation.outs + outs_from_running,
                AdvanceOptions {
                    take_extra_base: false,
                },
            );
            return self.package(input, outcome, merge(outs_from_running, events, adv));
        }

        let mut probs = outcome_probabilities(
            &input.rates,
            &input.pitcher,
            input.defense,
            input.park.run_factor,
        );
        if input.calls.hit_and_run && input.situation.bases.first.is_some() {
            apply_hit_and_run(&mut probs);
        }
        let outcome = self.draw_outcome(&probs);
        let take_extra = self.take_extra_base(outcome, &bases, input.calls.hit_and_run);
        let adv = advance(
            &bases,
            &input.hitter_id,
            outcome,
            input.situation.outs + outs_from_running,
            AdvanceOptions {
                take_extra_base: take_extra,
            },
        );
        self.package(input, outcome, merge(outs_from_running, events, adv))
    }

    fn take_extra_base(&mut self, outcome: PlateOutcome, bases: &Bases, hit_and_run: bool) -> bool {
        let chance = matches!(
            outcome,
            PlateOutcome::Single | PlateOutcome::Double | PlateOutcome::BuntSingle
        ) && bases.first.is_some();
        if !chance {
            return false;
        }
        if hit_and_run && matches!(outcome, PlateOutcome::Single | PlateOutcome::BuntSingle) {
            return true;
        }
        self.rng.gen::<f64>() < EXTRA_BASE_RATE
    }

    fn draw_bunt(&mut self, bases: &Bases, outs: u8) -> PlateOutcome {
        let roll = self.rng.gen::<f64>();
        if roll < BUNT_HIT_RATE {
            PlateOutcome::BuntSingle
        } else if roll < BUNT_HIT_RATE + BUNT_SAC_RATE && outs < 2 && bases.any() {
            PlateOutcome::BuntSacrifice
        } else {
            PlateOutcome::BuntOut
        }
    }

    fn draw_outcome(&mut self, probs: &OutcomeProbs) -> PlateOutcome {
        let roll = self.rng.gen::<f64>();
        let table = [
            (PlateOutcome::Strikeout, probs.k),
            (PlateOutcome::Walk, probs.bb),
            (PlateOutcome::HitByPitch, probs.hbp),
            (PlateOutcome::Single, probs.single),
            (PlateOutcome::Double, probs.double),
            (PlateOutcome::Triple, probs.triple),
            (PlateOutcome::HomeRun, probs.hr),
            (PlateOutcome::BipOut, probs.bip_out),
        ];
        let mut cursor = 0.0;
        for (outcome, probability) in table {
            cursor += probability;
            if roll < cursor {
                return outcome;
            }
        }
        PlateOutcome::BipOut
    }

    fn package(&mut self, input: &PaInput, outcome: PlateOutcome, adv: Advancement) -> PaResult {
        let (pitches, count) = self.pitches_for(outcome);
        let in_play = matches!(
            outcome,
            PlateOutcome::Single
                | PlateOutcome::Double
                | PlateOutcome::Triple
                | PlateOutcome::HomeRun
                | PlateOutcome::BipOut
                | PlateOutcome::BuntSingle
                | PlateOutcome::BuntOut
                | PlateOutcome::BuntSacrifice
        );
        PaResult {
            batter_id: input.hitter_id.clone(),
            pitcher_id: input.pitcher_id.clone(),
            outcome,
            batter_completed: adv.batter_completed,
            change: BaseOutRunChange {
                outs_added: adv.outs_added,
                runs_scored: adv.runs_scored,
                bases: adv.bases,
            },
            pitches,
            count,
            baserunning: adv.events,
            fielding: Fielding {
                rating: input.defense,
                in_play,
            },
        }
    }

    fn pitches_for(&mut self, outcome: PlateOutcome) -> (Vec<Pitch>, Count) {
        match outcome {
            PlateOutcome::IntentionalWalk => four_balls(),
            PlateOutcome::Strikeout => {
                let balls = self.rng.gen_range(0..4);
                self.sequence(balls, 2, true, PitchKind::SwingingStrike)
            }
            PlateOutcome::Walk => {
                let strikes = self.rng.gen_range(0..3);
                self.sequence(3, strikes, true, PitchKind::Ball)
            }
            PlateOutcome::HitByPitch => {
                let balls = self.rng.gen_range(0..4);
                let strikes = self.rng.gen_range(0..3);
                self.sequence(balls, strikes, true, PitchKind::HitByPitch)
            }
            PlateOutcome::CaughtStealing => {
                let kind = if self.rng.gen_bool(0.5) {
                    PitchKind::Ball
                } else {
                    PitchKind::CalledStrike
                };
                self.sequence(0, 0, false, kind)
            }
            _ => {
                let balls = self.rng.gen_range(0..4);
                let strikes = self.rng.gen_range(0..3);
                self.sequence(balls, strikes, true, PitchKind::InPlay)
            }
        }
    }

    fn sequence(
        &mut self,
        balls: u8,
        strikes: u8,
        fouls_at_two_strikes: bool,
        final_kind: PitchKind,
    ) -> (Vec<Pitch>, Count) {
        let mut kinds = Vec::new();
        kinds.extend(std::iter::repeat(PitchKind::Ball).take(balls as usize));
        kinds.extend(std::iter::repeat(PitchKind::CalledStrike).take(strikes as usize));
        kinds.shuffle(&mut self.rng);
        let mut built = CountBuilder::default();
        for kind in kinds {
            built.push(kind);
        }
        if fouls_at_two_strikes && built.strikes >= 2 {
            let fouls = self.rng.gen_range(0..3);
            for _ in 0..fouls {
                built.push(PitchKind::Foul);
            }
        }
        built.push(final_kind);
        built.finish()
    }
}

fn four_balls() -> (Vec<Pitch>, Count) {
    let mut built = CountBuilder::default();
    for _ in 0..4 {
        built.push(PitchKind::Ball);
    }
    built.finish()
}

fn merge(outs_before: u8, mut earlier: Vec<BaserunningEvent>, adv: Advancement) -> Advancement {
    earlier.extend(adv.events);
    Advancement {
        bases: adv.bases,
        outs_added: outs_before + adv.outs_added,
        runs_scored: adv.runs_scored,
        events: earlier,
        batter_completed: adv.batter_completed,
    }
}

#[derive(Default)]
struct CountBuilder {
    balls: u8,
    strikes: u8,
    pitches: Vec<Pitch>,
}

impl CountBuilder {
    fn push(&mut self, kind: PitchKind) {
        match kind {
            PitchKind::Ball => self.balls = (self.balls + 1).min(4),
            PitchKind::CalledStrike | PitchKind::SwingingStrike => {
                self.strikes = (self.strikes + 1).min(3);
            }
            PitchKind::Foul => {
                if self.strikes < 2 {
                    self.strikes += 1;
                }
            }
            PitchKind::InPlay | PitchKind::HitByPitch => {}
        }
        self.pitches.push(Pitch {
            kind,
            balls: self.balls,
            strikes: self.strikes,
        });
    }

    fn finish(self) -> (Vec<Pitch>, Count) {
        let count = self
            .pitches
            .last()
            .map(|pitch| Count {
                balls: pitch.balls,
                strikes: pitch.strikes,
            })
            .unwrap_or_default();
        (self.pitches, count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Half, Park, PrePaCalls, Situation};

    fn average_pitcher() -> PitcherRates {
        PitcherRates {
            k: LEAGUE_K,
            bb: LEAGUE_BB,
            hbp: LEAGUE_HBP,
            hr: LEAGUE_HR,
            h: LEAGUE_H,
        }
    }

    fn stub_300() -> HitterRates {
        HitterRates {
            k: 0.180,
            bb: 0.080,
            hbp: 0.010,
            single: 0.182,
            double: 0.050,
            triple: 0.006,
            hr: 0.035,
            bip_out: 0.457,
        }
    }

    #[test]
    fn league_pitcher_returns_the_hitter_card() {
        let hitter = stub_300();
        let probs = outcome_probabilities(&hitter, &average_pitcher(), 0.0, 1.0);
        assert!((probs.sum() - 1.0).abs() < 1e-9);
        assert!((probs.k - hitter.k).abs() < 1e-9);
        assert!((probs.bb - hitter.bb).abs() < 1e-9);
        assert!((probs.hbp - hitter.hbp).abs() < 1e-9);
        assert!((probs.single - hitter.single).abs() < 1e-9);
        assert!((probs.double - hitter.double).abs() < 1e-9);
        assert!((probs.triple - hitter.triple).abs() < 1e-9);
        assert!((probs.hr - hitter.hr).abs() < 1e-9);
        assert!((probs.bip_out - hitter.bip_out).abs() < 1e-9);
        assert!((probs.batting_average() - 0.300).abs() < 1e-9);
        assert!((card_batting_average(&hitter) - 0.300).abs() < 1e-9);
    }

    #[test]
    fn defense_moves_hits_and_outs_in_the_stated_direction() {
        let hitter = stub_300();
        let pitcher = average_pitcher();
        let even = outcome_probabilities(&hitter, &pitcher, 0.0, 1.0);
        let good = outcome_probabilities(&hitter, &pitcher, 10.0, 1.0);
        let poor = outcome_probabilities(&hitter, &pitcher, -10.0, 1.0);
        assert!(good.non_hr_hits() < even.non_hr_hits());
        assert!(good.bip_out > even.bip_out);
        assert!(poor.non_hr_hits() > even.non_hr_hits());
        assert!(poor.bip_out < even.bip_out);
        assert!((good.hr - even.hr).abs() < 1e-12);
        assert!((good.k - even.k).abs() < 1e-12);
    }

    #[test]
    fn neutral_park_is_a_no_op_and_a_higher_factor_raises_home_runs() {
        let hitter = stub_300();
        let pitcher = average_pitcher();
        let neutral = outcome_probabilities(&hitter, &pitcher, 0.0, 1.0);
        let hitter_park = outcome_probabilities(&hitter, &pitcher, 0.0, 1.2);
        assert!((neutral.hr - hitter.hr).abs() < 1e-9);
        assert!(hitter_park.hr > neutral.hr);
        assert!((hitter_park.sum() - 1.0).abs() < 1e-9);
    }

    #[test]
    fn single_with_a_runner_on_second_scores_him() {
        let bases = Bases {
            first: None,
            second: Some("r2".into()),
            third: None,
        };
        let adv = advance(
            &bases,
            "batter",
            PlateOutcome::Single,
            0,
            AdvanceOptions {
                take_extra_base: false,
            },
        );
        assert_eq!(adv.runs_scored, 1);
        assert_eq!(adv.outs_added, 0);
        assert_eq!(adv.bases.first.as_deref(), Some("batter"));
        assert!(adv.bases.second.is_none());
    }

    #[test]
    fn walk_with_the_bases_loaded_forces_one_run() {
        let bases = Bases {
            first: Some("r1".into()),
            second: Some("r2".into()),
            third: Some("r3".into()),
        };
        let adv = advance(
            &bases,
            "batter",
            PlateOutcome::Walk,
            1,
            AdvanceOptions {
                take_extra_base: false,
            },
        );
        assert_eq!(adv.runs_scored, 1);
        assert_eq!(adv.bases.first.as_deref(), Some("batter"));
        assert_eq!(adv.bases.second.as_deref(), Some("r1"));
        assert_eq!(adv.bases.third.as_deref(), Some("r2"));
    }

    #[test]
    fn ball_in_play_out_holds_runners() {
        let bases = Bases {
            first: Some("r1".into()),
            second: None,
            third: Some("r3".into()),
        };
        let adv = advance(
            &bases,
            "batter",
            PlateOutcome::BipOut,
            0,
            AdvanceOptions {
                take_extra_base: true,
            },
        );
        assert_eq!(adv.outs_added, 1);
        assert_eq!(adv.runs_scored, 0);
        assert_eq!(adv.bases, bases);
    }

    #[test]
    fn extra_base_on_a_single_sends_the_runner_to_third() {
        let bases = Bases {
            first: Some("r1".into()),
            second: None,
            third: None,
        };
        let adv = advance(
            &bases,
            "batter",
            PlateOutcome::Single,
            0,
            AdvanceOptions {
                take_extra_base: true,
            },
        );
        assert_eq!(adv.bases.third.as_deref(), Some("r1"));
        assert_eq!(adv.bases.first.as_deref(), Some("batter"));
        assert!(adv.bases.second.is_none());
        assert!(adv
            .events
            .iter()
            .any(|event| matches!(event, BaserunningEvent::TookExtraBase { .. })));
    }

    #[test]
    fn home_run_with_the_bases_loaded_scores_four() {
        let bases = Bases {
            first: Some("r1".into()),
            second: Some("r2".into()),
            third: Some("r3".into()),
        };
        let adv = advance(
            &bases,
            "batter",
            PlateOutcome::HomeRun,
            2,
            AdvanceOptions {
                take_extra_base: false,
            },
        );
        assert_eq!(adv.runs_scored, 4);
        assert_eq!(adv.bases, Bases::empty());
    }

    #[test]
    fn intentional_walk_is_four_balls_and_only_when_called() {
        let input = sample_input(false);
        let mut called = input.clone();
        called.calls.intentional_walk = true;
        let mut sim = Sim::from_seed(7);
        let result = sim.resolve(&called);
        assert_eq!(result.outcome, PlateOutcome::IntentionalWalk);
        assert_eq!(result.pitches.len(), 4);
        assert!(result
            .pitches
            .iter()
            .all(|pitch| pitch.kind == PitchKind::Ball));
        assert_eq!(
            result.count,
            Count {
                balls: 4,
                strikes: 0
            }
        );

        let mut quiet = Sim::from_seed(7);
        let other = quiet.resolve(&input);
        assert_ne!(other.outcome, PlateOutcome::IntentionalWalk);
    }

    #[test]
    fn bunt_without_a_call_does_not_happen() {
        let input = sample_input(false);
        let mut sim = Sim::from_seed(11);
        for _ in 0..200 {
            let result = sim.resolve(&input);
            assert!(!matches!(
                result.outcome,
                PlateOutcome::BuntOut | PlateOutcome::BuntSingle | PlateOutcome::BuntSacrifice
            ));
        }
    }

    fn sample_input(intentional_walk: bool) -> PaInput {
        PaInput {
            hitter_id: "batter".into(),
            hitter_name: "Batter".into(),
            rates: stub_300(),
            wrc_plus: 140.0,
            pitcher_id: "pitcher".into(),
            pitcher_name: "Pitcher".into(),
            pitcher: average_pitcher(),
            defense: 0.0,
            situation: Situation {
                inning: 1,
                half: Half::Top,
                outs: 0,
                bases: Bases::empty(),
                away_score: 0,
                home_score: 0,
                pitcher_fatigue: 10.0,
                pitcher_ceiling: 100.0,
                postseason: false,
            },
            park: Park {
                id: "neutral".into(),
                run_factor: 1.0,
            },
            weather: Some("crosswind".into()),
            calls: PrePaCalls {
                intentional_walk,
                ..PrePaCalls::default()
            },
        }
    }
}
