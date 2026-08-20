"""Parse Cursor MCP SQL dump files (outer JSON + untrusted-data wrapper)."""
from __future__ import annotations

import json
import re
from pathlib import Path


def extract_payload(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        outer = json.loads(text)
    except json.JSONDecodeError:
        outer = None
    if isinstance(outer, dict) and isinstance(outer.get("result"), str):
        text = outer["result"]
    match = re.search(
        r"<untrusted-data-[0-9a-f-]+>\s*([\[{].*?)\s*</untrusted-data-[0-9a-f-]+>",
        text,
        re.S,
    )
    if not match:
        raise ValueError(f"no payload in {path}")
    return json.loads(match.group(1))


def unwrap_dump(payload):
    while isinstance(payload, list) and payload and isinstance(payload[0], dict) and "dump" in payload[0]:
        payload = payload[0]["dump"]
    while isinstance(payload, dict) and set(payload.keys()) == {"dump"}:
        payload = payload["dump"]
    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "schema" in payload[0]:
        return payload[0]["schema"]
    return payload


if __name__ == "__main__":
    import sys

    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    payload = extract_payload(src)
    dest.write_text(json.dumps(unwrap_dump(payload), indent=2), encoding="utf-8")
    print(dest)
