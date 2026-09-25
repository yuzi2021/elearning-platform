# Repository audit record

## Baseline

- One Django app (`courses`) with Django templates and DRF.
- SQLite was the immediately runnable fallback; `DATABASE_URL` already existed
  for PostgreSQL and Neon-style pooled URLs.
- Redis was configured for Celery and Channels, not application caching.
- Celery contained two real email tasks and one artificial console task.
- Channels implemented public/anonymous course chat without enrollment checks.
- External integrations: ZenQuotes, Open-Meteo with database cache, and optional
  TextRazor with keyword fallback.
- Role profiles: learner and instructor; several REST/HTML/WebSocket boundaries
  were missing or too broad, and profile APIs exposed personal fields.
- UI: generic Bootstrap, duplicate catalog controls, an overloaded technical
  home page, weak role orientation, extensive inline CSS/JS, and unsafe chat DOM
  insertion.
- Deployment assets existed, but retained SkillPath naming and no CI workflow.
- Baseline verification: 60 tests discovered and passed in 104.562 seconds;
  Django checks and migration-drift checks passed with explicit development
  values.

## Final implementation summary

- Provider-independent PostgreSQL configuration retained; eLearning naming,
  environment sample, Docker services, Render blueprint, startup, and standard
  `seed_demo` command aligned.
- Added optional Redis application caching, structured logging, configurable
  external timeouts, liveness/readiness separation, and production static checks.
- Added database rating/counter constraints, aggregate query improvements, bulk
  notification writes, and an atomic download counter.
- Tightened role, ownership, enrollment, resource, profile, notification, REST,
  and WebSocket boundaries; removed personal fields from API serializers.
- Removed the artificial Celery task; genuine emails now dispatch after commit
  and report failure honestly.
- Rebuilt the template shell and core learner/instructor workflows with a small
  responsive, accessibility-conscious design system and contextual states.
- Added API documentation, deterministic demo operations, PostgreSQL/Redis CI,
  and 25 meaningful tests for hardened behavior, bringing discovery to 85.

## Verification limitations

- Docker was not installed on the audit host, so Compose was not executed.
- No Neon/Render credentials or external deployment resources were available;
  there is no verified live URL.
- PostgreSQL execution is configured in CI but requires the workflow to run on
  GitHub before a passing CI claim is made.
- No formal accessibility audit, browser-device lab, coverage percentage, or
  production usage claim is made.
