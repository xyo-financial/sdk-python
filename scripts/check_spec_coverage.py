#!/usr/bin/env python3
"""Verify the hand-written XYO Python client still covers the OpenAPI specification.

The Python SDK is hand-written on httpx rather than machine-generated, so
nothing mechanically forces it to stay in step with `xyo-financial/specs`. This
script is that guard: it fails when the spec declares a request path the client
never issues, which is the signal a maintainer needs to implement it by hand.

Scope and limits: this checks request paths only. It deliberately does not try
to verify HTTP methods, schemas or field names, because matching those against
hand-written code produces false positives that train maintainers to ignore the
check. Schema drift is caught by the respx-backed suite under tests/.

Usage:
    python3 scripts/check_spec_coverage.py path/to/openapi.yml
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENT_SOURCES = (
    REPO_ROOT / "src" / "xyo" / "client.py",
    REPO_ROOT / "src" / "xyo" / "async_client.py",
)


def is_covered(path: str, source: str) -> bool:
    """Report whether the client issues a request against this specification path.

    URLs are built with f-strings, so the literal appears unquoted in the source.
    A concrete path must be followed by a terminator, otherwise a longer route
    sharing its prefix (``/transaction`` inside ``/transaction/collection``)
    would mask its absence. A templated path can only be matched on the fixed
    prefix ahead of the first placeholder.
    """
    prefix, sep, _ = path.partition("{")
    if sep:
        return prefix in source
    return re.search(re.escape(path) + r"""(?=["'?\s]|$)""", source) is not None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <openapi.yml>", file=sys.stderr)
        return 2

    try:
        import yaml
    except ImportError:
        print("error: PyYAML is required (pip install pyyaml)", file=sys.stderr)
        return 2

    spec_path = Path(argv[1])
    if not spec_path.is_file():
        print(f"error: specification not found: {spec_path}", file=sys.stderr)
        return 2

    with spec_path.open(encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)

    paths = (spec or {}).get("paths") or {}
    if not paths:
        print("error: specification declares no paths", file=sys.stderr)
        return 2

    missing = []
    for source_path in CLIENT_SOURCES:
        if not source_path.is_file():
            print(f"error: client source not found: {source_path}", file=sys.stderr)
            return 2

    source = "\n".join(p.read_text(encoding="utf-8") for p in CLIENT_SOURCES)
    checked = ", ".join(str(p.relative_to(REPO_ROOT)) for p in CLIENT_SOURCES)

    spec_version = (spec.get("info") or {}).get("version", "unknown")
    print(f"Specification version: {spec_version}")
    print(f"Checking {len(paths)} path(s) against {checked}\n")

    for path in sorted(paths):
        methods = sorted(
            method.upper()
            for method in (paths[path] or {})
            if method.lower() in {"get", "put", "post", "delete", "patch", "head", "options"}
        )
        covered = is_covered(path, source)
        print(f"  [{'ok' if covered else 'MISSING'}] {path}  ({', '.join(methods) or 'no methods'})")
        if not covered:
            missing.append(path)

    if missing:
        print(
            f"\n{len(missing)} specification path(s) are not issued by the client:",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        print(
            "\nImplement them in src/xyo/client.py and src/xyo/async_client.py, then add coverage under tests/.",
            file=sys.stderr,
        )
        return 1

    print("\nAll specification paths are issued by the client.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
