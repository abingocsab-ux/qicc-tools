"""Add SITE_PIN to SWA app settings without printing the value.

az staticwebapp appsettings set replaces the whole set, so existing keys
are read and written back together with SITE_PIN.
Usage: python scripts/set_site_pin.py <pin>
"""
import json
import subprocess
import sys

AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        raise SystemExit("usage: python scripts/set_site_pin.py <pin>")
    pin = sys.argv[1].strip()
    raw = json.loads(subprocess.check_output(
        [AZ, "staticwebapp", "appsettings", "list", "-g", "rg-qicc-tools", "-n", "qicc-production", "-o", "json"],
        text=True,
    ))
    props = raw.get("properties") if isinstance(raw, dict) else None
    if not isinstance(props, dict) or not props:
        raise SystemExit("unexpected appsettings shape")
    props["SITE_PIN"] = pin
    subprocess.check_call(
        [
            AZ, "staticwebapp", "appsettings", "set",
            "-g", "rg-qicc-tools", "-n", "qicc-production",
            "--setting-names",
            *[f"{k}={v}" for k, v in props.items()],
        ]
    )
    print("SITE_PIN set (value not printed)")
    print("preserved keys:", ", ".join(sorted(props)))


if __name__ == "__main__":
    main()
