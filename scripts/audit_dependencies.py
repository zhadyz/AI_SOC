#!/usr/bin/env python3
"""Fail on dependency advisories not covered by a current, versioned mitigation."""
import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    exceptions = json.loads((ROOT / "docs/security/dependency-exceptions.json").read_text())
    with tempfile.TemporaryDirectory() as scratch:
        report = Path(scratch) / "audit.json"
        process = subprocess.run([sys.executable, "-m", "pip_audit", "--progress-spinner", "off", "--format", "json", "--output", str(report)], capture_output=True, text=True)
        if process.returncode not in (0, 1) or not report.exists():
            raise RuntimeError("Dependency audit did not complete: " + process.stderr[:500])
        data = json.loads(report.read_text())
    unresolved, mitigated = [], []
    for dependency in data["dependencies"]:
        exception = exceptions.get(dependency["name"], {})
        for vuln in dependency.get("vulns", []):
            item = {"package": dependency["name"], "version": dependency["version"], "id": vuln["id"], "fix_versions": vuln.get("fix_versions", [])}
            if (dependency["version"] == exception.get("version") and vuln["id"] in exception.get("ids", [])
                    and date.today() <= date.fromisoformat(exception["review_by"])):
                item["mitigation"] = exception["reason"]
                mitigated.append(item)
            else:
                unresolved.append(item)
    result = {"status": "failed" if unresolved else "passed_with_documented_mitigations",
              "packages_scanned": len(data["dependencies"]), "unresolved": unresolved, "mitigated": mitigated}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Scanned {len(data['dependencies'])} packages: {len(unresolved)} unresolved, {len(mitigated)} documented mitigations")
    return bool(unresolved)


if __name__ == "__main__":
    sys.exit(main())
