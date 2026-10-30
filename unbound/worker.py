import asyncio
import os
import uuid
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from .settings import Settings
from .store import Store
from .providers import make_provider
from .engine import Engine, EngineError
from .models import PHASES


async def process_once(store, provider, settings, checkpointer=None):
    owner = str(uuid.uuid4())
    rid = store.claim(owner, settings.provider, settings.model)
    if not rid:
        return False

    async def heartbeat():
        while True:
            await asyncio.sleep(10)
            if not store.heartbeat(rid, owner):
                return

    beat = asyncio.create_task(heartbeat())
    try:
        await (
            Engine(store, provider, settings, owner)
            .graph(checkpointer)
            .ainvoke(
                {"run_id": rid, "phase": PHASES[0]},
                {"configurable": {"thread_id": rid}, "recursion_limit": 30},
            )
        )
    except asyncio.CancelledError:
        # Release immediately on graceful shutdown; hard crashes recover on lease expiry.
        store.fail(rid, owner, "Worker interrupted; retry to resume committed phases")
        store.retry(rid)
        raise
    except EngineError as exc:
        store.fail(rid, owner, str(exc))
    except Exception as exc:
        store.fail(
            rid,
            owner,
            f"Internal {type(exc).__name__}; inspect installation/schema and retry. Provider payloads omitted for privacy.",
        )
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
    return True


async def serve():
    settings = Settings()
    settings.prepare()
    store = Store(settings.db)
    provider = make_provider(settings)
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db) as saver:

        async def loop():
            while True:
                if not await process_once(store, provider, settings, saver):
                    await asyncio.sleep(1)

        await asyncio.gather(
            *(loop() for _ in range(max(1, min(settings.worker_concurrency, 4))))
        )


def main():
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
