# Architecture Overview

TripCraft is split into a mobile client and a FastAPI backend.

## Mobile App

The mobile app is built with Expo Router and React Native. It contains:

- Authentication screens and token persistence through SecureStore.
- Adaptive quiz screens for travel preference discovery.
- Photo onboarding and review screens for image-based preference extraction.
- Country recommendation, itinerary generation, interactive map, profile, and friends flows.
- API access through `mobile/services/api.js`.

## Backend API

The backend is a FastAPI application organized by routers:

- `auth.py`: registration, login, and current-user lookup.
- `quiz.py`: adaptive quiz sessions, swipes, answers, clarification, and profile results.
- `ml.py`: image tagging, photo analysis, and photo-profile confirmation.
- `itinerary.py`: itinerary generation, plan reads, ratings, regeneration, replacement, and travel memory.
- `interactive_mode.py`: city and attraction exploration for interactive trip planning.
- `social.py`: friends, group trips, and group recommendations.

## Data Model

PostgreSQL stores users, quiz sessions, tag hierarchy, countries, cities, attractions, itinerary plans, ratings, friendships, and group trips.

Schema changes are managed through Alembic. See:

- `backend/alembic/versions/`
- `backend/MIGRATIONS.md`
- `docs/database_schema.svg`

## Recommendation Flow

1. The user completes either the adaptive quiz or photo onboarding.
2. The backend produces a weighted tag profile.
3. Country and itinerary ranking use tag overlap, hierarchy-aware scoring, diversity, budget, season, and feedback signals.
4. Itineraries are persisted and can be rated or regenerated.
5. Feedback updates the user's learned preference profile.

## Photo Analysis Flow

1. The mobile app sends 1-5 selected photos.
2. The FastAPI backend validates the payload and enqueues a Redis/RQ background job.
3. A dedicated ML worker runs CLIP-based image analysis and maps visual concepts to database tags.
4. The mobile app polls job status until the worker returns the generated photo profile.
5. The user reviews the inferred tags before confirming them.
6. Confirmed tags become a completed profile session and can drive recommendations.

## Evaluation

The `backend/evaluation/` folder contains scripts and summaries used to evaluate:

- Quiz profile recovery.
- Recommendation quality.
- Image-recognition precision, recall, and NDCG.
- Runtime and downstream itinerary effects.

The generated CSV/JSON/PNG result files are intentionally ignored when regenerable; summary Markdown files are kept for review.

## Production Hardening Roadmap

The current architecture is suitable for local development, academic evaluation, and portfolio review. A production deployment should add:

- Redis/RQ worker deployment with monitoring, retries, and autoscaling rules.
- External object storage for image uploads.
- Stronger rate limiting around expensive endpoints.
- CI checks for tests, linting, dependency validation, and migrations.
- EAS configuration and final mobile app identifiers.
