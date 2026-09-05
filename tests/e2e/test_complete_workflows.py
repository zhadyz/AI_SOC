"""Explicit live acceptance: any failed service or assertion fails the test."""
import pytest
from scripts.smoke_test import run

@pytest.mark.live
def test_complete_local_workflow():
    report = run(full=True)
    assert report["llm_exercised"] and report["full"]
