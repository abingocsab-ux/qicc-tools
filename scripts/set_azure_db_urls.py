"""Point SWA app settings at the copied Azure databases. Does not print secrets.

az staticwebapp appsettings set replaces the whole set, so existing keys
(including JWT_SECRET) are read and written back together with the new URLs.
"""
import json
import subprocess
from urllib.parse import urlparse, urlunparse

AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"


def az_json(args: list[str]):
    return json.loads(subprocess.check_output([AZ, *args, "-o", "json"], text=True))


def with_db(url: str, dbname: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path="/" + dbname))


def main() -> None:
    raw = az_json([
        "staticwebapp", "appsettings", "list",
        "-g", "rg-qicc-tools", "-n", "qicc-production",
    ])
    props = raw.get("properties") if isinstance(raw, dict) else None
    if not isinstance(props, dict) or not props:
        raise SystemExit("unexpected appsettings shape")
    src = props.get("DATABASE_URL") or props.get("COPPER_DATABASE_URL")
    if not src:
        raise SystemExit("DATABASE_URL missing")
    copper = with_db(src, "copper_traceability")
    qicc = with_db(src, "qicc_production")
    props["DATABASE_URL"] = copper
    props["COPPER_DATABASE_URL"] = copper
    props["QICC_DATABASE_URL"] = qicc
    subprocess.check_call(
        [
            AZ, "staticwebapp", "appsettings", "set",
            "-g", "rg-qicc-tools", "-n", "qicc-production",
            "--setting-names",
            *[f"{k}={v}" for k, v in props.items()],
        ]
    )
    print("Updated DATABASE_URL, COPPER_DATABASE_URL, QICC_DATABASE_URL")
    print("preserved keys:", ", ".join(sorted(props)))


if __name__ == "__main__":
    main()
