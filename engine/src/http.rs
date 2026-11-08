// ABOUTME: Stateless JSON routes for the engine: start, step, matchup, and health.
// ABOUTME: Every request carries the whole game state; the process keeps nothing between requests.
//! The engine's HTTP surface.
//!
//! `POST /start` opens a fixture with a seed. `POST /step` resolves exactly one plate
//! appearance from a state, an optional call, and a seed. `POST /matchup` reports the
//! outcome probabilities the next plate appearance will draw from. `GET /health` answers
//! App Platform. The caller holds the state. The same state, call, and seed give the same result.

use axum::body::Bytes;
use axum::extract::DefaultBodyLimit;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::de::DeserializeOwned;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::game::{Game, GameError};
use crate::model::{GameFixture, PrePaCalls};
use crate::service::{self, Matchup, Stepped};

/// A finished extra-inning game is a few hundred kilobytes. This leaves room without being unbounded.
const BODY_LIMIT_BYTES: usize = 16 * 1024 * 1024;

pub fn router() -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/start", post(start))
        .route("/step", post(step))
        .route("/matchup", post(matchup))
        .layer(DefaultBodyLimit::max(BODY_LIMIT_BYTES))
}

#[derive(Deserialize)]
struct StartRequest {
    fixture: GameFixture,
    seed: u64,
}

#[derive(Deserialize)]
struct StepRequest {
    state: Game,
    #[serde(default)]
    call: Option<String>,
    seed: u64,
}

#[derive(Deserialize)]
struct MatchupRequest {
    state: Game,
}

async fn health() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}

async fn start(body: Bytes) -> Result<Json<Value>, HttpError> {
    let request: StartRequest = parse(&body)?;
    let game = service::start(request.fixture, request.seed).map_err(HttpError::Game)?;
    Ok(Json(json!({ "state": game })))
}

async fn step(body: Bytes) -> Result<Json<Stepped>, HttpError> {
    let request: StepRequest = parse(&body)?;
    let call = match request.call.as_deref() {
        None => None,
        Some(name) => Some(named_call(name)?),
    };
    service::step(request.state, call, request.seed)
        .map(Json)
        .map_err(HttpError::Game)
}

async fn matchup(body: Bytes) -> Result<Json<Matchup>, HttpError> {
    let request: MatchupRequest = parse(&body)?;
    service::matchup(&request.state)
        .map(Json)
        .map_err(HttpError::Game)
}

fn parse<T: DeserializeOwned>(body: &[u8]) -> Result<T, HttpError> {
    serde_json::from_slice(body).map_err(|err| HttpError::BadRequest(err.to_string()))
}

fn named_call(name: &str) -> Result<PrePaCalls, HttpError> {
    let mut calls = PrePaCalls::default();
    match name {
        "bunt" => calls.bunt = true,
        "intentional_walk" => calls.intentional_walk = true,
        "steal" => calls.steal = true,
        "hit_and_run" => calls.hit_and_run = true,
        "infield_in" => calls.infield_in = true,
        _ => return Err(HttpError::BadCall),
    }
    Ok(calls)
}

enum HttpError {
    Game(GameError),
    BadRequest(String),
    BadCall,
}

impl IntoResponse for HttpError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            Self::Game(GameError::GameOver) => (
                StatusCode::CONFLICT,
                "The game is final. There is no next plate appearance.".to_string(),
            ),
            Self::Game(err) => (StatusCode::UNPROCESSABLE_ENTITY, err.to_string()),
            Self::BadRequest(message) => (StatusCode::BAD_REQUEST, message),
            Self::BadCall => (
                StatusCode::BAD_REQUEST,
                "The call must be bunt, intentional_walk, steal, hit_and_run, infield_in, or omitted."
                    .to_string(),
            ),
        };
        (status, Json(json!({ "error": message }))).into_response()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use http_body_util::BodyExt;
    use serde_json::{json, Value};
    use tower::ServiceExt;

    use crate::game::Game;
    use crate::model::{load_json, GameFixture, PlateOutcome};

    fn fixture() -> GameFixture {
        let path = format!("{}/fixtures/game.json", env!("CARGO_MANIFEST_DIR"));
        load_json(&path).expect("fixture")
    }

    async fn exchange(request: Request<Body>) -> (StatusCode, Value) {
        let response = router().oneshot(request).await.expect("engine response");
        let status = response.status();
        let bytes = response
            .into_body()
            .collect()
            .await
            .expect("body")
            .to_bytes();
        let value = serde_json::from_slice(&bytes).unwrap_or(Value::Null);
        (status, value)
    }

    async fn post(uri: &str, body: Value) -> (StatusCode, Value) {
        exchange(
            Request::builder()
                .method("POST")
                .uri(uri)
                .header("content-type", "application/json")
                .body(Body::from(body.to_string()))
                .unwrap(),
        )
        .await
    }

    async fn started(seed: u64) -> Value {
        let (status, body) = post("/start", json!({ "fixture": fixture(), "seed": seed })).await;
        assert_eq!(status, StatusCode::OK, "{body}");
        body["state"].clone()
    }

    fn game(state: &Value) -> Game {
        serde_json::from_value(state.clone()).expect("game state")
    }

    #[tokio::test]
    async fn health_answers() {
        let (status, body) = exchange(
            Request::builder()
                .uri("/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["status"], "ok");
    }

    #[tokio::test]
    async fn start_returns_the_opening_state() {
        let state = started(7).await;
        let opening = game(&state);
        assert_eq!(opening.inning, 1);
        assert_eq!(opening.outs, 0);
        assert!(opening.results.is_empty());
        assert!(opening.home.pitcher_slot.is_some());
        assert_eq!(
            started(7).await,
            state,
            "the same seed opened a different game"
        );
    }

    #[tokio::test]
    async fn start_rejects_a_missing_seed() {
        let (status, body) = post("/start", json!({ "fixture": fixture() })).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(body["error"].as_str().unwrap().contains("seed"));
    }

    #[tokio::test]
    async fn two_steps_follow_one_another() {
        let state = started(1).await;
        let (status, first) = post("/step", json!({ "state": state, "seed": 11 })).await;
        assert_eq!(status, StatusCode::OK, "{first}");
        let after_first = game(&first["state"]);
        assert_eq!(after_first.results.len(), 1);
        assert_eq!(
            serde_json::to_value(&after_first.results[0]).unwrap(),
            first["result"]
        );

        let (status, second) = post(
            "/step",
            json!({ "state": first["state"], "call": null, "seed": 12 }),
        )
        .await;
        assert_eq!(status, StatusCode::OK, "{second}");
        let after_second = game(&second["state"]);
        assert_eq!(after_second.results.len(), 2);
        assert_eq!(
            after_second.results[0], after_first.results[0],
            "the first plate appearance was played again"
        );
        assert_ne!(
            after_second.results[1].batter_id, after_second.results[0].batter_id,
            "the second step did not advance the batting order"
        );
    }

    #[tokio::test]
    async fn the_same_state_call_and_seed_give_the_same_result() {
        let state = started(3).await;
        let request = json!({ "state": state, "call": "hit_and_run", "seed": 99 });
        let (_, one) = post("/step", request.clone()).await;
        let (_, two) = post("/step", request).await;
        assert_eq!(one, two);

        let mut seeds_differ = false;
        for seed in 0..20u64 {
            let (_, other) = post("/step", json!({ "state": state, "seed": seed })).await;
            if other["result"] != one["result"] {
                seeds_differ = true;
                break;
            }
        }
        assert!(seeds_differ, "the seed does not reach the draw");
    }

    #[tokio::test]
    async fn a_whole_game_plays_through_the_step_route() {
        let mut state = started(5).await;
        let mut steps = 0u64;
        while !game(&state).is_final() {
            steps += 1;
            assert!(steps < 2_000, "the game did not end");
            let (status, body) = post("/step", json!({ "state": state, "seed": steps })).await;
            assert_eq!(status, StatusCode::OK, "{body}");
            state = body["state"].clone();
        }
        let (status, body) = post("/step", json!({ "state": state, "seed": 0 })).await;
        assert_eq!(status, StatusCode::CONFLICT);
        assert!(body["error"].as_str().unwrap().contains("final"));
    }

    #[tokio::test]
    async fn an_intentional_walk_is_honored() {
        let state = started(2).await;
        let (status, body) = post(
            "/step",
            json!({ "state": state, "call": "intentional_walk", "seed": 4 }),
        )
        .await;
        assert_eq!(status, StatusCode::OK, "{body}");
        let outcome: PlateOutcome =
            serde_json::from_value(body["result"]["outcome"].clone()).unwrap();
        assert_eq!(outcome, PlateOutcome::IntentionalWalk);
    }

    #[tokio::test]
    async fn a_bunt_is_honored() {
        let state = started(2).await;
        let (status, body) = post(
            "/step",
            json!({ "state": state, "call": "bunt", "seed": 4 }),
        )
        .await;
        assert_eq!(status, StatusCode::OK, "{body}");
        let outcome: PlateOutcome =
            serde_json::from_value(body["result"]["outcome"].clone()).unwrap();
        assert!(matches!(
            outcome,
            PlateOutcome::BuntSingle | PlateOutcome::BuntSacrifice | PlateOutcome::BuntOut
        ));
    }

    #[tokio::test]
    async fn a_steal_with_a_runner_on_first_is_honored() {
        let mut opening = game(&started(2).await);
        opening.bases.first = Some(opening.away.lineup[8].id.clone());
        let state = serde_json::to_value(&opening).unwrap();
        let (status, body) = post(
            "/step",
            json!({ "state": state, "call": "steal", "seed": 4 }),
        )
        .await;
        assert_eq!(status, StatusCode::OK, "{body}");
        let events = body["result"]["baserunning"].as_array().unwrap();
        assert!(
            events
                .iter()
                .any(|event| event.get("StolenBase").is_some()
                    || event.get("CaughtStealing").is_some()),
            "no steal was tried: {events:?}"
        );
    }

    #[tokio::test]
    async fn a_hit_and_run_is_accepted() {
        let state = started(2).await;
        let (status, body) = post(
            "/step",
            json!({ "state": state, "call": "hit_and_run", "seed": 4 }),
        )
        .await;
        assert_eq!(status, StatusCode::OK, "{body}");
    }

    #[tokio::test]
    async fn infield_in_holds_the_runner_on_third_on_a_ground_out() {
        let mut opening = game(&started(2).await);
        opening.bases.third = Some(opening.away.lineup[8].id.clone());
        let state = serde_json::to_value(&opening).unwrap();
        let mut ground_outs = 0;
        for seed in 0..200u64 {
            let (status, body) = post(
                "/step",
                json!({ "state": state, "call": "infield_in", "seed": seed }),
            )
            .await;
            assert_eq!(status, StatusCode::OK, "{body}");
            let outcome: PlateOutcome =
                serde_json::from_value(body["result"]["outcome"].clone()).unwrap();
            if outcome == PlateOutcome::GroundOut {
                ground_outs += 1;
                assert_eq!(body["result"]["change"]["runs_scored"], 0);
                assert_eq!(
                    body["state"]["bases"]["third"].as_str(),
                    opening.bases.third.as_deref()
                );
            }
        }
        assert!(ground_outs > 0, "no ground out in 200 seeds");
    }

    #[tokio::test]
    async fn a_fixture_without_batted_balls_plays_with_league_rates() {
        let opening = game(&started(2).await);
        let original: Value = serde_json::from_str(
            &std::fs::read_to_string(format!("{}/fixtures/game.json", env!("CARGO_MANIFEST_DIR")))
                .unwrap(),
        )
        .unwrap();
        assert!(original["away"]["lineup"][0].get("batted_balls").is_none());
        assert_eq!(
            opening.away.lineup[0].batted_balls,
            crate::model::BattedBallRates::default()
        );
        assert_eq!(
            opening.home.pitchers[0].batted_balls,
            crate::model::BattedBallRates::default()
        );
    }

    #[tokio::test]
    async fn an_unknown_call_is_rejected() {
        let state = started(2).await;
        let (status, body) = post(
            "/step",
            json!({ "state": state, "call": "squeeze", "seed": 4 }),
        )
        .await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(body["error"].as_str().unwrap().contains("intentional_walk"));
    }

    #[tokio::test]
    async fn a_malformed_state_is_rejected() {
        let (status, body) = post("/step", json!({ "state": { "inning": 1 }, "seed": 4 })).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(body["error"].is_string());
    }

    #[tokio::test]
    async fn matchup_reports_the_draw_without_drawing() {
        let state = started(8).await;
        let (status, body) = post("/matchup", json!({ "state": state })).await;
        assert_eq!(status, StatusCode::OK, "{body}");
        let opening = game(&state);
        assert_eq!(body["batter_id"], opening.away.lineup[0].id);
        assert_eq!(
            body["pitcher_id"].as_str(),
            opening.home.pitcher_slot.as_deref()
        );
        assert_eq!(body["pitcher_entering"], false);
        let probabilities = body["probabilities"].as_object().unwrap();
        for key in [
            "k", "bb", "hbp", "single", "double", "triple", "hr", "bip_out",
        ] {
            assert!(probabilities[key].is_f64(), "{key} is missing");
        }
        let sum: f64 = probabilities
            .values()
            .map(|value| value.as_f64().unwrap())
            .sum();
        assert!((sum - 1.0).abs() < 1e-9, "probabilities sum to {sum}");

        let (_, again) = post("/matchup", json!({ "state": state })).await;
        assert_eq!(again, body, "matchup is not a pure read");
    }

    #[tokio::test]
    async fn matchup_names_the_pitcher_who_will_enter_on_an_empty_mound() {
        let mut opening = game(&started(8).await);
        let starter = opening.home.pitcher_slot.take().unwrap();
        opening.home.in_game.retain(|id| id != &starter);
        opening.home.unavailable.push(starter);
        let entering = opening.home.available[0].clone();
        let state = serde_json::to_value(&opening).unwrap();
        let (status, body) = post("/matchup", json!({ "state": state })).await;
        assert_eq!(status, StatusCode::OK, "{body}");
        assert_eq!(body["pitcher_id"], entering);
        assert_eq!(body["pitcher_entering"], true);
    }
}
