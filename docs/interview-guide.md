# Technical interview guide

## Likely questions

1. **Why use Django as a monolith rather than microservices?**  Explain the
   cohesive domain, transactional workflows, operational simplicity, and lack
   of a scaling boundary that would justify service extraction.
2. **How are learner and instructor permissions enforced?**  Cover profile-based
   roles, view decorators, ownership checks, active-enrollment checks, DRF object
   permissions/queryset scoping, and equivalent WebSocket authorization.
3. **Why dispatch Celery tasks with `transaction.on_commit`?**  A worker must not
   query a row that can still roll back; optional dispatch failure must not undo
   the committed core action.
4. **Why do email tasks not automatically retry?**  SMTP outcomes can be
   ambiguous and duplicate delivery is possible. Describe an outbox/delivery
   ledger as the route to idempotent retry.
5. **What does Redis do here?**  In the complete stack: Celery broker/result
   backend, distributed Channels layer, and application cache. It is not the
   relational system of record.
6. **How does the WebSocket path stay secure?**  Session authentication through
   `AuthMiddlewareStack`, rejection before group membership, active
   enrollment/ownership lookup, payload validation, database persistence, and
   safe DOM text rendering.
7. **How does external API failure behave?**  Configurable timeouts, response
   validation, structured logs, quote/local fallback, stale weather cache, and
   deterministic TextRazor fallback with source labels.
8. **How did you address query efficiency?**  `select_related`,
   `prefetch_related`, aggregate annotations, bulk notification creation, and an
   atomic `F()` counter update tied to observed access patterns.
9. **Why Neon plus Render, and what are the limitations?**  Provider-independent
   `DATABASE_URL`, pooled PostgreSQL with SSL, persistence independent of web
   redeploys, free-tier cold starts, single-instance WebSockets without Redis,
   and no ephemeral media assumptions.
10. **What would you build next?**  Modules/lessons, genuine completion events,
    instructor-scoped assignments, an idempotent email outbox, abuse controls for
    a public writable demo, and a formal accessibility review—only as justified
    by product requirements.

## Code to understand before the interview

| Topic | Files | What to trace |
|---|---|---|
| Settings and deployment modes | `config/settings.py`, `.env.example`, `render.yaml` | Environment parsing, PostgreSQL pooling, optional Redis/Celery/Channels/media |
| HTTP/ASGI entry points | `config/urls.py`, `config/asgi.py`, `courses/routing.py` | URL routing and the HTTP/WebSocket split |
| Relational model | `courses/models.py`, `courses/migrations/` | Foreign keys, constraints, signals, role profiles, atomic counter |
| HTML access control | `courses/views.py` | Role decorators, ownership, active enrollment, optimized querysets |
| REST access control | `courses/api.py`, `courses/serializers.py` | Status codes, scoping, privacy, external fallbacks, aggregates |
| Async boundary | `courses/services.py`, `courses/tasks.py` | Optional dispatch, `on_commit`, task failure semantics |
| Real-time path | `courses/consumers.py`, `courses/templates/courses/chat.html` | Connection authorization, validation, persistence, safe rendering |
| Educational UX | `templates/base.html`, `courses/templates/courses/home.html`, `course_detail.html`, `courses/static/courses/app.css` | Orientation, role-specific actions, honest progress limits, responsive system |
| Tests | `courses/tests.py`, `courses/test_security.py`, `courses/test_realtime.py` | Baseline vs hardened cases and failure-path intent |
| CI and operations | `.github/workflows/ci.yml`, `compose.yaml`, `start.sh`, `courses/health.py` | Service dependencies, migrations, checks, liveness/readiness |

## A concise architecture explanation

“Daphne serves both Django HTTP and Channels WebSocket traffic. Django and DRF
share one relational domain model backed by PostgreSQL in full/deployed modes.
Core writes commit first; optional email work is queued to Celery afterward.
Redis provides the task broker, shared channel layer, and cache in the complete
stack. External integrations are bounded by timeouts and have labelled fallback
paths. The public-demo mode keeps PostgreSQL as the system of record but can run
without optional workers or Redis, with the reduced real-time capability stated
explicitly.”
