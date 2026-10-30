# Implementation plan

Implement the supplied UNBOUND INNOVATION ENGINE v3.0 and AGENTIC BLUEPRINT in the existing repository, retaining its history.

1. Define strict Pydantic input/output contracts, versioned creative rules, mode rubrics and all 12 lenses.
2. Implement a LangGraph state machine with four concurrent creative workers, deferred evaluation, novelty/coverage repair, wildcard extraction, two synthesis levels, evidence review, scoring, execution blueprint and validation.
3. Persist durable jobs, phase outputs, stable concept IDs, model metadata, worker activity and checkpoints in SQLite. Use a process-wide database lease and transactionally commit each phase. Resume interrupted phases without duplicating outputs.
4. Add environment-selected live LangChain adapters, explicit offline mock provider, optional Exa and Wolfram adapters, bounded retries/timeouts and sanitized diagnostics.
5. Serve FastAPI endpoints and an escaped, mobile-responsive dashboard with polling, history, detailed results and JSON/Markdown exports.
6. Test orchestration invariants, concurrency, errors/recovery, persistence, API and browser behavior. Run live inference only with configured credentials; distinguish it from mock demonstrations.
7. Supply reproducible dependency lock, container/systemd deployment, backup/recovery instructions and measured verification evidence.

Defaults: GENERAL for ambiguous AUTO intent; 35 ideas, 5 wildcards, 5 hybrids, 3 meta-hybrids, 5 shortlisted candidates; all 12 lens tags; three attempts per operation; 120-second provider timeout. SQLite first, PostgreSQL deferred. Generated experiment blueprints never execute code or external operations.
