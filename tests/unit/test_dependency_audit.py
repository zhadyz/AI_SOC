"""Dependency policy survives advisory aliases without broadening exceptions."""
import json
from subprocess import CompletedProcess

import pytest

from scripts import audit_dependencies


@pytest.mark.parametrize(
    "advisory_id,aliases,version,review_by,expected_failure",
    [
        ("CVE-2026-45833", [], "1.5.9", "2999-01-01", False),
        ("PYSEC-2026-3814", ["CVE-2026-45833"], "1.5.9", "2999-01-01", False),
        ("PYSEC-2026-3814", [], "1.5.9", "2999-01-01", True),
        ("UNREVIEWED", ["UNREVIEWED-ALIAS"], "1.5.9", "2999-01-01", True),
        ("PYSEC-2026-3814", ["CVE-2026-45833"], "1.5.10", "2999-01-01", True),
        ("PYSEC-2026-3814", ["CVE-2026-45833"], "1.5.9", "2000-01-01", True),
    ],
)
def test_audit_enforces_version_expiry_and_advisory_identity(
    tmp_path, monkeypatch, advisory_id, aliases, version, review_by, expected_failure
):
    policy_dir = tmp_path / "docs/security"
    policy_dir.mkdir(parents=True)
    (policy_dir / "dependency-exceptions.json").write_text(json.dumps({
        "chromadb": {
            "version": "1.5.9", "ids": ["CVE-2026-45833"],
            "review_by": review_by, "reason": "Test mitigation",
        }
    }))
    output = tmp_path / "result.json"
    monkeypatch.setattr(audit_dependencies, "ROOT", tmp_path)
    monkeypatch.setattr(audit_dependencies.sys, "argv", ["audit", "--output", str(output)])

    def run_audit(command, **kwargs):
        audit_dependencies.Path(command[command.index("--output") + 1]).write_text(json.dumps({
            "dependencies": [{
                "name": "chromadb", "version": version,
                "vulns": [{"id": advisory_id, "aliases": aliases, "fix_versions": []}],
            }]
        }))
        return CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(audit_dependencies.subprocess, "run", run_audit)
    assert audit_dependencies.main() is expected_failure
    result = json.loads(output.read_text())
    assert len(result["unresolved"]) == int(expected_failure)
    assert len(result["mitigated"]) == int(not expected_failure)
