# Setup, security, operations and deployment

## Environment and credentials

Use `.env.example`, with real secrets only in an untracked `.env` or mode-0600 service environment file. `UNBOUND_PROVIDER` and `UNBOUND_MODEL` must match in API and worker. Credentials: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `UNBOUND_API_KEY` plus compatible base URL. Research: optional `EXA_API_KEY`, optional `WOLFRAM_APP_ID`. Configure no credentials in frontend code. All SDK failures are sanitized before storage; do not publish raw provider logs. Inputs/reports can themselves be private business data.

Bind the API to loopback. For network use set a long `UNBOUND_OWNER_PASSWORD`; authenticate as username **owner**. Use an HTTPS reverse proxy and expose only TCP 443 (plus 80 for TLS provisioning if needed). Basic auth is only suitable over TLS. Browser mutation requests are same-origin checked; no cross-origin API access is enabled. No provider keys are sent to the browser. Keep the gateway's Host header intact. Because the API is behind TLS termination, mutation checks accept matching HTTPS origins based on a configured public origin (see below); never trust arbitrary forwarded host headers.

The model is not a trusted command executor. Outputs are JSON validated, displayed with textContent and never evaluated as HTML or executable code. Exa excerpts are untrusted evidence, not instructions. Semantic quality, safety and evidence relevance still require owner review. Restrict file access and back up sensitive data securely.

## Docker Compose on an authorized persistent host

1. Install Docker with Compose using the host's supported method.
2. Clone your pinned reviewed repository revision, prepare `.env`, and set owner password/public origin for network access.
3. Run `docker compose up --build -d`. API and worker independently restart after reboot when Docker starts. Only loopback port 8000 is published.
4. Configure the existing authenticated TLS gateway or Caddy using `deploy/Caddyfile.example` with an owned domain. Verify authentication before sharing a URL.
5. Check `docker compose ps`, `/health`, then submit a real run and inspect the worker. A successful container start alone does not prove inference works.

Never run `docker compose down -v` against data you need. Use `docker compose stop` to retain history. Docker builds never copy `.env`, data or credentials; `.dockerignore` enforces this.

## systemd alternative

Create a dedicated `unbound` account; install this revision and virtualenv under `/opt/unbound`. Create `/var/lib/unbound` owned by that account, mode 0700. Create `/etc/unbound/environment` mode 0600 with provider settings and absolute paths:

```
UNBOUND_DB=/var/lib/unbound/unbound.sqlite
UNBOUND_CHECKPOINT_DB=/var/lib/unbound/checkpoints.sqlite
```

Install the two `deploy/*.service` units under `/etc/systemd/system/`, run `systemctl daemon-reload`, then `systemctl enable --now unbound-api unbound-worker`. Do not apply these units over unrelated services. Both processes restart after host reboot; pending and interrupted runs are recovered. Generated blueprints never become system services.

## Backup and restore

Stop the worker and API for a consistent two-database backup. Copy both SQLite databases and any `-wal`/`-shm` files as a set, plus your securely stored service configuration, to an encrypted restricted location. Prefer SQLite's backup API after stopping writes; never copy only a live WAL-mode main file. Restart both services. Test restoration in an isolated directory with mock mode and no public exposure. Provider secrets are in environment configuration, not the run database.

Restore with both processes stopped, compatible application revision and correct file ownership. Keep backups private; run inputs and research may contain confidential material.

## Update and rollback

Back up first. Fetch and inspect a pinned commit, install its locked dependencies, run tests, then restart API and worker together. Keep the previous code revision/venv and backup. Roll back both code and the corresponding database snapshot if schema compatibility changes. This initial version only creates missing tables; future schema changes need explicit migrations. Never delete existing history as a recovery shortcut.

## Troubleshooting

- 503 on run creation: missing selected-provider credentials. Supply securely and restart both processes.
- QUEUED forever: worker absent, mismatched provider/model, wrong DB path or file permissions. Health endpoint is API liveness only.
- FAILED provider stage: check model ID, credentials, quota, network, timeout or schema support. Retry resumes completed phases. Three exhausted repairs never become a false successful report.
- After hard crash: wait up to 60 seconds for the lease to expire; restart the matching worker.
- Research UNAVAILABLE: optional credentials absent or integration failed. Basic ideation can finish; assumptions remain unverified.
- 403 from a phone: network mode needs owner authentication and protected HTTPS; use a configured public origin, not permissive CORS.
- Insufficient distinct ideas: inspect novelty exclusions and provider quality. Repairs are bounded; switch to a more capable model rather than lowering the 35-idea requirement.

Actual persistent-host installation, TLS, reboot behavior and physical-phone access must be verified on the selected host; local tests do not establish those outcomes.
