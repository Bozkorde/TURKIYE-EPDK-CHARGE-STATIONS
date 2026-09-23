#!/usr/bin/env python3
"""Builds stations.json for the Şarj Haritası app from EPDK's public charging-station feed.

The feed is the one EPDK publishes under the Şarj Hizmeti Yönetmeliği's free-access platform
(Md. 17/2, 30/1): every licensed station with its coordinates and sockets. Its quota is tight
and undocumented — a second call seconds after the first gets HTTP 429 — so a run makes exactly
one request and never retries. The app reads the published file, never EPDK itself.

    build_stations.py                      fetch once and write stations.json
    build_stations.py --save-raw feed.json also keep the raw response
    build_stations.py --from-raw feed.json rebuild from a saved response, no request
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://apigateway.epdk.gov.tr/sarjIstasyonlari"
USER_AGENT = "SarjHaritasi-data (+https://github.com/Bozkorde/TURKIYE-EPDK-CHARGE-STATIONS)"
OUT = Path(__file__).resolve().parent.parent / "stations.json"
MIN_STATIONS = 5000        # far below the ~13k public stations; anything under this is a broken feed
MIN_SHARE_OF_PREVIOUS = 0.9
STALE_AFTER_DAYS = 14      # quota refusals are skipped quietly until the data gets this old


def fetch():
    request = urllib.request.Request(URL, data=b"{}", method="GET", headers={
        "Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def in_turkey(lat, lng):
    # Same loose box the app uses: every station lives inside it, placeholders like (0, 0) don't.
    return lat is not None and lng is not None and 35 <= lat <= 43 and 25 <= lng <= 45


_TR_UPPER = str.maketrans("ıi", "Iİ")


def display_brand(raw):
    """Brands arrive as each operator typed them: "zes", "eşarj", "VOLTRUN". An all-lowercase word
    gets a capital first letter ("Zes", "İspark"); anything else is left alone. All-caps names are
    not re-cased, because whether their I lowers to ı or i depends on the word's language:
    "EN YAKIT" wants "Yakıt", "CHARGING" wants "Charging"."""
    def word(match):
        w = match.group()
        if w != w.lower() or not w[:1].isalpha():
            return w
        return w[:1].translate(_TR_UPPER).upper() + w[1:]
    return re.sub(r"[^\s-]+", word, " ".join(raw.split()))


def station(record):
    """One feed record in the app's Station shape, or None if it can't be placed on the map."""
    code = (record.get("sarjIstasyonuNo") or "").strip()
    lat, lng = number(record.get("enlem")), number(record.get("boylam"))
    if not code or not in_turkey(lat, lng):
        return None

    ac, dc, chademo = [], [], []
    for socket in record.get("soketler") or []:
        kind = (socket.get("soketTuru") or "").upper()
        power = number(socket.get("soketGucu")) or 0
        if "CHADEMO" in kind:
            chademo.append(power)
        elif (socket.get("soketTipi") or "").upper() == "DC" or kind.startswith("DC"):
            dc.append(power)
        else:
            ac.append(power)

    def count(powers):
        return len(powers) or None

    def strongest(powers):
        top = max(powers, default=0)
        return round(top) if top > 0 else None

    brand = display_brand(record.get("marka") or "")
    name = (record.get("sarjIstasyonuAdi") or "").strip()
    address = (record.get("adres") or "").strip()
    return {
        "id": code, "istasyonKodu": code, "marka": brand, "lat": lat, "lng": lng,
        "acAdet": count(ac), "acGuc": strongest(ac),
        "dcAdet": count(dc), "dcGuc": strongest(dc),
        "chademoAdet": count(chademo), "chademoGuc": strongest(chademo),
        "officialName": name or f"{brand} Şarj Noktası",
        "fullAddress": address, "hasExplicitAddress": bool(address),
    }


def days_since_last_publish():
    try:
        stamp = subprocess.run(["git", "log", "-1", "--format=%ct", "--", OUT.name], cwd=OUT.parent,
                               capture_output=True, text=True, check=True).stdout.strip()
        return (time.time() - int(stamp)) / 86400 if stamp else None
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-raw", type=Path)
    parser.add_argument("--from-raw", type=Path)
    args = parser.parse_args()

    if args.from_raw:
        feed = json.loads(args.from_raw.read_text(encoding="utf-8"))
    else:
        try:
            feed = fetch()
        except (urllib.error.URLError, TimeoutError) as error:
            # Quota refusals and EPDK outages are routine: skip quietly and try tomorrow. Any
            # other HTTP error means the feed itself changed, and that needs a person.
            code = getattr(error, "code", None)
            if code is not None and code != 429 and code < 500:
                raise
            age = days_since_last_publish()
            print(f"EPDK unavailable ({error}); last publish "
                  + (f"{age:.1f} days ago" if age is not None else "never"))
            sys.exit(1 if age is None or age > STALE_AFTER_DAYS else 0)
        if args.save_raw:
            args.save_raw.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")

    records = feed.get("data") if isinstance(feed, dict) else feed
    if not isinstance(records, list):
        sys.exit(f"Unexpected response shape: {str(feed)[:300]}")

    public = [r for r in records if (r.get("hizmetSekli") or "").strip().casefold().startswith("halka")]
    stations = sorted(filter(None, map(station, public)), key=lambda s: s["id"])
    print(f"feed: {len(records)} stations, {len(public)} public, {len(stations)} placeable")

    if len(stations) < MIN_STATIONS:
        sys.exit(f"Refusing to publish only {len(stations)} stations")
    if OUT.exists():
        previous = len(json.loads(OUT.read_text(encoding="utf-8")))
        if len(stations) < previous * MIN_SHARE_OF_PREVIOUS:
            sys.exit(f"Refusing to publish {len(stations)} stations over the previous {previous}")

    # One station per line: compact, and a daily diff shows exactly which stations changed.
    lines = (json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in stations)
    OUT.write_text("[\n" + ",\n".join(lines) + "\n]\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
