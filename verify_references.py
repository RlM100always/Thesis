"""Verify thesis bibliography metadata against Crossref/DataCite and live URLs."""

from __future__ import annotations

import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote

import requests

BIB = Path("thesis_report/Bibliography.bib")
OUT_JSON = Path("output/reference_verification.json")
OUT_MD = Path("output/reference_verification.md")
HEADERS = {"User-Agent": "B-SMART-thesis-reference-audit/1.0 (academic verification)"}


def field(block: str, name: str) -> str | None:
    match = re.search(rf"(?ims)^\s*{re.escape(name)}\s*=\s*\{{(.*?)\}}\s*,?\s*$", block)
    return match.group(1).strip() if match else None


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"\\[A-Za-z]+", "", text)
    text = text.replace("{", "").replace("}", "").replace("--", "-")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def fetch_metadata(doi: str) -> tuple[str, dict | None, str]:
    encoded = quote(doi, safe="")
    try:
        response = requests.get(f"https://api.crossref.org/works/{encoded}", headers=HEADERS, timeout=25)
        if response.ok:
            return "Crossref", response.json().get("message", {}), "verified"
    except requests.RequestException:
        pass
    try:
        response = requests.get(f"https://api.datacite.org/dois/{encoded}", headers=HEADERS, timeout=25)
        if response.ok:
            attrs = response.json().get("data", {}).get("attributes", {})
            titles = attrs.get("titles") or []
            creators = attrs.get("creators") or []
            converted = {
                "title": [titles[0].get("title", "")] if titles else [],
                "published": {"date-parts": [[attrs.get("publicationYear")]]},
                "author": [{"family": c.get("familyName", ""), "given": c.get("givenName", "")} for c in creators],
                "URL": attrs.get("url"),
            }
            return "DataCite", converted, "verified"
    except requests.RequestException:
        pass
    return "none", None, "not found"


def metadata_year(meta: dict) -> str:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        parts = (meta.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return ""


def main() -> None:
    text = BIB.read_text(encoding="utf-8")
    blocks = ["@" + chunk for chunk in re.split(r"(?m)^@", text) if chunk.strip()]
    records = []
    for block in blocks:
        header = re.match(r"@\w+\s*\{\s*([^,]+),", block)
        if not header:
            continue
        key = header.group(1).strip()
        title, year, doi, url = field(block, "title"), field(block, "year"), field(block, "doi"), field(block, "url")
        record = {"key": key, "bib_title": title, "bib_year": year, "doi": doi, "url": url}
        if doi:
            registry, meta, registry_status = fetch_metadata(doi)
            record["registry"] = registry
            record["registry_status"] = registry_status
            if meta:
                remote_title = (meta.get("title") or [""])[0]
                remote_year = metadata_year(meta)
                similarity = SequenceMatcher(None, clean(title), clean(remote_title)).ratio()
                remote_clean = clean(remote_title)
                local_clean = clean(title)
                containment = bool(len(remote_clean) >= 7 and remote_clean in local_clean)
                record.update({
                    "registry_title": remote_title,
                    "registry_year": remote_year,
                    "title_similarity": round(similarity, 4),
                    "title_match": similarity >= .70 or containment,
                    "year_match": not year or not remote_year or str(year) == str(remote_year),
                })
        try:
            target = url or (f"https://doi.org/{doi}" if doi else None)
            response = requests.get(target, headers=HEADERS, timeout=25, allow_redirects=True) if target else None
            record["url_http_status"] = response.status_code if response is not None else None
            record["url_accessible"] = bool(response is not None and response.status_code < 400)
            record["resolved_url"] = response.url if response is not None else None
        except requests.RequestException as exc:
            record["url_http_status"] = None
            record["url_accessible"] = False
            record["url_error"] = str(exc)[:180]
        if key == "wfp2026prices":
            try:
                api = requests.get(
                    "https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-bangladesh",
                    headers=HEADERS, timeout=25,
                )
                payload = api.json() if api.ok else {}
                record["official_dataset_api_status"] = api.status_code
                record["official_dataset_api_verified"] = bool(
                    api.ok and payload.get("success") and payload.get("result", {}).get("name")
                    == "wfp-food-prices-for-bangladesh"
                )
            except requests.RequestException:
                record["official_dataset_api_verified"] = False
        official_non_doi_url = bool(url and "doi.org/" not in url.lower() and record.get("url_accessible", False))
        record["verified"] = bool(
            (record.get("registry_status") == "verified" and record.get("title_match", False))
            or official_non_doi_url
            or record.get("official_dataset_api_verified", False)
            or (not doi and record.get("url_accessible", False))
        )
        records.append(record)
        print(f"{key:28s} {'OK' if record['verified'] else 'CHECK'}")
        time.sleep(.08)

    summary = {
        "generated_at": "2026-09-07",
        "bibliography": str(BIB),
        "count": len(records),
        "verified_count": sum(bool(r["verified"]) for r in records),
        "all_verified": all(bool(r["verified"]) for r in records),
        "method": "DOI title checked against Crossref/DataCite; non-DOI records checked at official URL",
        "records": records,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Thesis reference verification", "",
        f"Date: {summary['generated_at']}", "",
        f"Verified: **{summary['verified_count']} / {summary['count']}**", "",
        "| Key | Registry/source | DOI/URL | Title match | Year match | Status |", "|---|---|---|---:|---:|---|",
    ]
    for r in records:
        link = r.get("doi") or r.get("url") or "-"
        lines.append(f"| `{r['key']}` | {r.get('registry', 'official URL')} | {link} | "
                     f"{r.get('title_match', '-')} | {r.get('year_match', '-')} | "
                     f"{'verified' if r['verified'] else 'manual check required'} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("count", "verified_count", "all_verified")}, indent=2))


if __name__ == "__main__":
    main()
