//! The play API and the one-page demo.
//!
//! `POST /api/games` opens the fixture. `GET /api/games/:id` reads the saved game.
//! `POST /api/games/:id/plate-appearances` resolves exactly one plate appearance.
//! Games live in the process. This page is one person stepping that game.

use std::sync::{Arc, Mutex};

use axum::body::Bytes;
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{Html, IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde_json::{json, Value};

use crate::model::PrePaCalls;
use crate::session::{PlayBook, PlayError, SavedGame};

type Shared = Arc<Mutex<PlayBook>>;

pub fn demo_router(book: PlayBook) -> Router {
    Router::new()
        .route("/", get(index))
        .route("/api/games", post(start_game))
        .route("/api/games/:id", get(read_game))
        .route("/api/games/:id/plate-appearances", post(step_game))
        .with_state(Arc::new(Mutex::new(book)))
}

async fn index() -> Html<&'static str> {
    Html(include_str!("demo.html"))
}

async fn start_game(State(book): State<Shared>) -> Result<Json<SavedGame>, HttpError> {
    let mut book = lock(&book);
    book.open_fixture().map(Json).map_err(HttpError::Play)
}

async fn read_game(
    State(book): State<Shared>,
    Path(id): Path<String>,
) -> Result<Json<SavedGame>, HttpError> {
    let book = lock(&book);
    book.read(&id).map(Json).map_err(HttpError::Play)
}

async fn step_game(
    State(book): State<Shared>,
    Path(id): Path<String>,
    body: Bytes,
) -> Result<Json<SavedGame>, HttpError> {
    let call = parse_call(&body)?;
    let mut book = lock(&book);
    book.step(&id, call).map(Json).map_err(HttpError::Play)
}

fn lock(book: &Shared) -> std::sync::MutexGuard<'_, PlayBook> {
    book.lock().expect("play book lock")
}

fn parse_call(body: &[u8]) -> Result<Option<PrePaCalls>, HttpError> {
    if body.iter().all(|byte| byte.is_ascii_whitespace()) {
        return Ok(None);
    }
    let parsed: Value = serde_json::from_slice(body).map_err(|_| HttpError::BadCall)?;
    let Some(object) = parsed.as_object() else {
        return Err(HttpError::BadCall);
    };
    match object.get("call") {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(name)) => named_call(name).map(Some),
        Some(_) => Err(HttpError::BadCall),
    }
}

fn named_call(name: &str) -> Result<PrePaCalls, HttpError> {
    let mut calls = PrePaCalls::default();
    match name {
        "bunt" => calls.bunt = true,
        "intentional_walk" => calls.intentional_walk = true,
        "steal" => calls.steal = true,
        "hit_and_run" => calls.hit_and_run = true,
        _ => return Err(HttpError::BadCall),
    }
    Ok(calls)
}

enum HttpError {
    Play(PlayError),
    BadCall,
}

impl IntoResponse for HttpError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            Self::Play(PlayError::Missing) => (
                StatusCode::NOT_FOUND,
                "This server does not have that game. It may have been started in a process that has stopped.".to_string(),
            ),
            Self::Play(PlayError::Final) => (
                StatusCode::CONFLICT,
                "The game is final. There is no next plate appearance.".to_string(),
            ),
            Self::BadCall => (
                StatusCode::BAD_REQUEST,
                "The call must be bunt, intentional_walk, steal, hit_and_run, or omitted.".to_string(),
            ),
            Self::Play(PlayError::Failed(message)) => (StatusCode::INTERNAL_SERVER_ERROR, message),
        };
        (status, Json(json!({ "error": message }))).into_response()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::Request;
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    async fn exchange(app: &Router, request: Request<Body>) -> (StatusCode, Value) {
        let response = app
            .clone()
            .oneshot(request)
            .await
            .expect("play api response");
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

    fn saved(value: Value) -> SavedGame {
        serde_json::from_value(value).expect("saved game")
    }

    #[tokio::test]
    async fn two_plate_appearances_advance_and_keep_the_first() {
        let app = demo_router(PlayBook::new());
        let (status, body) = exchange(
            &app,
            Request::builder()
                .method("POST")
                .uri("/api/games")
                .body(Body::empty())
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let started = saved(body);
        assert!(started.state.plate_appearances.is_empty());

        let read_uri = format!("/api/games/{}", started.id);
        let (status, body) = exchange(
            &app,
            Request::builder()
                .uri(&read_uri)
                .body(Body::empty())
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let parked = saved(body);
        assert_eq!(parked, started);

        let step_uri = format!("/api/games/{}/plate-appearances", started.id);
        let (status, body) = exchange(
            &app,
            Request::builder()
                .method("POST")
                .uri(&step_uri)
                .header("content-type", "application/json")
                .body(Body::from("{}"))
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let first = saved(body);
        assert_eq!(first.state.plate_appearances.len(), 1);

        let (status, body) = exchange(
            &app,
            Request::builder()
                .method("POST")
                .uri(&step_uri)
                .header("content-type", "application/json")
                .body(Body::from(r#"{"call":"bunt"}"#))
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let second = saved(body);
        assert_eq!(second.state.plate_appearances.len(), 2);
        assert_eq!(
            second.state.plate_appearances[0], first.state.plate_appearances[0],
            "the first plate appearance was played again"
        );
        assert_ne!(
            second.state.plate_appearances[1].batter_id,
            second.state.plate_appearances[0].batter_id,
            "the second call did not advance the batting order"
        );

        let (status, body) = exchange(
            &app,
            Request::builder()
                .uri(&read_uri)
                .body(Body::empty())
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let after = saved(body);
        assert_eq!(after, second);

        let (status, body) = exchange(
            &app,
            Request::builder()
                .uri(&read_uri)
                .body(Body::empty())
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let still = saved(body);
        assert_eq!(still.state.plate_appearances.len(), 2);
        assert_eq!(still, after);
    }

    #[tokio::test]
    async fn a_bad_call_leaves_the_saved_game() {
        let app = demo_router(PlayBook::new());
        let (_, body) = exchange(
            &app,
            Request::builder()
                .method("POST")
                .uri("/api/games")
                .body(Body::empty())
                .unwrap(),
        )
        .await;
        let started = saved(body);
        let (status, body) = exchange(
            &app,
            Request::builder()
                .method("POST")
                .uri(format!("/api/games/{}/plate-appearances", started.id))
                .header("content-type", "application/json")
                .body(Body::from(r#"{"call":"squeeze"}"#))
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(body["error"].as_str().unwrap().contains("intentional_walk"));
        let (status, body) = exchange(
            &app,
            Request::builder()
                .uri(format!("/api/games/{}", started.id))
                .body(Body::empty())
                .unwrap(),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert!(saved(body).state.plate_appearances.is_empty());
    }

    #[tokio::test]
    async fn page_includes_the_empty_state() {
        let app = demo_router(PlayBook::new());
        let response = app
            .oneshot(Request::builder().uri("/").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        let html = String::from_utf8(bytes.to_vec()).unwrap();
        assert!(html.contains("No game has been started."));
        assert!(html.contains("Opening the fixture and saving the game."));
        assert!(html.contains("Resolving this plate appearance."));
    }
}
