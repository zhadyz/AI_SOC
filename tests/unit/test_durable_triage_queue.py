"""Accepted jobs survive an interrupted worker and completed results survive restart."""
import asyncio
from unittest.mock import AsyncMock
import pytest

from services.alert_triage.worker_pool import WorkerPool


async def test_processing_job_recovers_after_worker_interruption(tmp_path):
    path = str(tmp_path / "jobs.sqlite")
    entered = asyncio.Event()
    gate = asyncio.Event()
    async def interrupted(data):
        entered.set()
        await gate.wait()
    first = WorkerPool(interrupted, worker_count=1, store_path=path)
    await first.start()
    job_id = first.submit({"alert_id": "durable-1", "rule_level": 12})
    await asyncio.wait_for(entered.wait(), 2)
    for task in first._workers:
        task.cancel()
    await asyncio.gather(*first._workers, return_exceptions=True)
    analyze = AsyncMock(return_value={"alert_id": "durable-1", "severity": "high"})
    second = WorkerPool(analyze, worker_count=1, store_path=path)
    await second.start()
    await asyncio.wait_for(second._queue.join(), 2)
    assert second.get_job(job_id).status == "completed"
    analyze.assert_awaited_once_with({"alert_id": "durable-1", "rule_level": 12})
    assert second.stats["jobs_recovered"] == 1
    await second.stop()
    third = WorkerPool(analyze, worker_count=1, store_path=path)
    await third.start()
    assert third.queue_depth == 0
    assert third.get_job(job_id).result["severity"] == "high"
    await third.stop()


async def test_full_queue_rejects_new_job_without_losing_accepted_work(tmp_path):
    analyze = AsyncMock(return_value={"done": True})
    pool = WorkerPool(analyze, store_path=str(tmp_path / "jobs.sqlite"), queue_capacity=1, worker_count=1)
    accepted = pool.submit({"alert_id": "first"})
    with pytest.raises(asyncio.QueueFull):
        pool.submit({"alert_id": "second"})
    await pool.start()
    await asyncio.wait_for(pool._queue.join(), 2)
    assert pool.get_job(accepted).status == "completed"
    analyze.assert_awaited_once()
    await pool.stop()


def test_persistence_failure_prevents_acceptance(tmp_path, monkeypatch):
    pool = WorkerPool(AsyncMock(), store_path=str(tmp_path / "jobs.sqlite"))
    def failed(*args):
        raise RuntimeError("disk unavailable")
    monkeypatch.setattr(pool.store, "save", failed)
    with pytest.raises(RuntimeError):
        pool.submit({"alert_id": "never-accepted"})
    assert pool.queue_depth == 0 and not pool._results
