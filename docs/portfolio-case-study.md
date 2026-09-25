# eLearning Platform — Full-Stack Learning Platform & Backend Engineering

**Project label:** University software project, subsequently redesigned and
productionised as an independent portfolio project.

## Portfolio summary

I revisited a substantial university eLearning application and developed it
into a coherent, production-oriented portfolio system. The work retained its
Django identity while hardening role and ownership boundaries, moving the
deployment model toward PostgreSQL, separating optional infrastructure from
core workflows, and redesigning the learner/instructor experience around clear
next actions rather than decorative metrics.

The platform combines server-rendered Django workflows with a scoped REST API,
Celery email tasks dispatched after database commit, Redis-backed caching and
distributed Channels support in the full stack, authenticated WebSocket course
discussion, signal-driven notifications, and external APIs with timeout,
validation, cache, stale-data, and deterministic fallback behavior.

The educational UX work was equally important: role-aware dashboards, protected
course resources, clear enrollment state, focused reading widths, contextual
empty/error/degraded states, accessible navigation and forms, and responsive
layouts. I deliberately did not display progress percentages because the data
model does not contain genuine completion events.

## Technology

Python · Django 5.2 · Django REST Framework · PostgreSQL · Redis · Celery ·
Django Channels · WebSockets · Daphne · Docker Compose · GitHub Actions ·
WhiteNoise · Automated Django Testing

## Evidence and outcomes

- Grew the verified suite from 60 baseline tests to 85 meaningful tests,
  including end-to-end ASGI WebSocket coverage and optional-dependency failure
  paths.
- Added PostgreSQL/Redis CI services, migration-drift checks, deployment checks,
  production static collection, deterministic demo seeding, and separate
  liveness/readiness endpoints.
- Enforced learner/instructor, enrollment, ownership, profile, notification, and
  WebSocket boundaries while minimizing API exposure of personal fields.
- Made external services and asynchronous work degrade without rolling back
  successful core learning actions.
- Replaced an overloaded academic dashboard with a calm, role-specific,
  responsive learning interface grounded in the schema's actual capabilities.

## Key decisions

I kept the system as a Django monolith because the operational and domain scope
does not justify microservices. I kept templates rather than introducing React
solely for modernity. PostgreSQL is the stable deployment database; SQLite is a
convenience fallback. Redis and Celery remain visible in the full architecture,
but the public web tier can operate without them and states the resulting
limitations. Email tasks do not auto-retry because delivery is not idempotent;
an outbox/delivery ledger would be the next step before enabling retries.

## What I learned

Productionising an existing system is less about adding tools than defining
boundaries: which data is public, which action requires which role, what must
commit before background work begins, which dependency is optional, what a
health signal really means, and which UX claims the underlying data can support.

## Suggested CV bullets

- Redesigned and productionised a university Django eLearning platform with
  PostgreSQL-oriented configuration, scoped REST APIs, deterministic demo data,
  Docker Compose, deployment health checks, and PostgreSQL/Redis GitHub Actions
  CI.
- Hardened learner/instructor authorization across HTML, REST, downloadable
  resources, and authenticated Channels WebSockets; added database constraints
  and privacy-conscious serializers.
- Implemented graceful degradation for Celery/Redis and three external APIs,
  including post-commit task dispatch, optional cache failure handling, stale
  weather data, deterministic NLP fallback, and structured logging.
- Reworked the educational UX into responsive role-aware dashboards and course
  workflows, increasing the verified Django test suite from 60 to 85 tests.

## Limitations

This is a demonstration-ready learning platform, not an enterprise LMS or a
production-proven service. It does not yet model modules, lessons, assignments,
or completion progress; no formal accessibility audit or user study has been
performed; and the external Render/Neon deployment must be provisioned and
verified by the repository owner before a live URL can be claimed.
