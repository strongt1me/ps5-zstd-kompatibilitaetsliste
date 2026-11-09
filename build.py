#!/usr/bin/env python3
"""Baut die PS5-ZSTD-Kompatibilitaetsliste (PDF, CHANGELOG, README) aus der Quell-Datenbank.

Quelle: https://theweil.github.io/PS5-ZSTD-Compatibility/ (CC BY 4.0)
Aufruf:  python build.py            -> baut alles, schreibt state.json/CHANGELOG/README/PDF
         python build.py --dry-run  -> nur Ausgabe der Aenderungen, nichts schreiben
Exit-Code 0 immer; Datei .changed wird angelegt, wenn es Aenderungen gab.
"""
import json, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
BASE = "https://theweil.github.io/PS5-ZSTD-Compatibility"
PDF_NAME = "PS5-ZSTD-Kompatibilitaetsliste.pdf"
DRY = "--dry-run" in sys.argv

STATUS_DE = {"ok": "Läuft", "fail": "Läuft nicht", "mixed": "Widersprüchlich", "unknown": "Unbestätigt"}
STATUS_ORDER = ["ok", "fail", "mixed", "unknown"]
TITLE_OVERRIDES = {"unidentified-p-030": "Unbekannter Titel (vermutlich A Plague Tale)"}
CJK = re.compile(r"[　-鿿＀-￯]")


def fetch(name):
    with urllib.request.urlopen(f"{BASE}/data/{name}", timeout=60) as r:
        return json.load(r)


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def translate(note, tr):
    """Chinesische Hinweise nach Deutsch; rein chinesische Namensanmerkungen entfallen."""
    if not note:
        return None
    if note in tr:
        return tr[note] or None
    m = re.fullmatch(r"([\d.]+)(?: / (\d+)G)?(?:（(.+)）)?", note)
    if m:
        v, size, who = m.groups()
        s = f"Version {v}" + (f" / {size} GB" if size else "") + (f" ({who})" if who else "")
        return s
    if CJK.search(note):
        print(f"WARNUNG: Hinweis nicht übersetzt, wird ausgelassen: {note!r}", file=sys.stderr)
        return None
    return note


def build_games():
    games = fetch("games.json")["games"]
    tests = fetch("tests.json")["tests"]
    tr = load_json(ROOT / "data" / "translations.json", {})
    manual = load_json(ROOT / "data" / "manual.json", {"games": []})["games"]

    rows = {}
    for g in games:
        title = TITLE_OVERRIDES.get(g["id"]) or g["title_en"] or g["title_original"]
        rows[g["id"]] = {"id": g["id"], "title": title, "ppsa": [], "regions": [], "results": [],
                         "formats": [], "testers": [], "notes": []}
    for t in tests:
        r = rows.get(t["game_id"])
        if not r:
            continue
        for p in t.get("ppsa_all") or ([t["ppsa"]] if t.get("ppsa") else []):
            if p not in r["ppsa"]:
                r["ppsa"].append(p)
        for x in t.get("regions") or ([t["region"]] if t.get("region") else []):
            if x.upper() != "UNKNOWN" and x not in r["regions"]:
                r["regions"].append(x)
        r["results"].append(t["result"])
        fmt = (t.get("compression") or "unknown").upper()
        if fmt != "UNKNOWN" and fmt not in r["formats"]:
            r["formats"].append(fmt)
        for x in t.get("tester") or []:
            if x not in r["testers"]:
                r["testers"].append(x)
        for k in ("notes", "symptom"):
            n = translate(t.get(k), tr)
            if n and not any(n in x or x in n for x in r["notes"]):
                r["notes"].append(n)
        if t.get("game_version") and not any(f"Version {t['game_version']}" in n or t["game_version"] in n for n in r["notes"]):
            r["notes"].append(f"Version {t['game_version']}")
        if t.get("runtime_version"):
            r["notes"].append(f"Runtime {t['runtime_version']}")
        if t.get("tested_at"):
            r["notes"].append(f"getestet am {datetime.fromisoformat(t['tested_at']).strftime('%d.%m.%Y')}")

    # eigene, manuell gepflegte Eintraege (falls die Quelle sie noch nicht hat)
    have = " ".join(r["title"].lower() for r in rows.values())
    for m in manual:
        if m["match"].lower() in have:
            continue
        rows[m["id"]] = {"id": m["id"], "title": m["title"], "ppsa": m["ppsa"], "regions": m["regions"],
                         "results": m["results"], "formats": m["formats"], "testers": m["testers"],
                         "notes": m["notes"]}

    out = []
    for r in rows.values():
        res = set(r["results"])
        if "pass" in res and ("fail" in res):
            st = "mixed"
        elif "pass" in res and "unknown" not in res:
            st = "ok"
        elif "fail" in res:
            st = "fail"
        else:
            st = "unknown"
        out.append({"id": r["id"], "title": r["title"], "ppsa": ", ".join(r["ppsa"]) or "–",
                    "region": "/".join(r["regions"]) or "–", "status": st,
                    "format": "/".join(r["formats"]) or "–", "tester": ", ".join(r["testers"]) or "–",
                    "notes": "; ".join(r["notes"]), "tests": len(r["results"])})
    out.sort(key=lambda g: g["title"].lower())
    return out


def diff(old, new):
    added, changed = [], []
    for g in new:
        o = old.get(g["id"])
        if o is None:
            added.append(g)
        else:
            what = []
            if o["status"] != g["status"]:
                what.append(f"Status: {STATUS_DE[o['status']]} → {STATUS_DE[g['status']]}")
            if o["format"] != g["format"]:
                what.append(f"Format: {o['format']} → {g['format']}")
            if o["tests"] != g["tests"]:
                what.append(f"Testberichte: {o['tests']} → {g['tests']}")
            if what:
                changed.append((g, "; ".join(what)))
    removed = [o for i, o in old.items() if i not in {g['id'] for g in new}]
    return added, changed, removed


def esc(s):
    return s.replace("|", "\\|")


def changelog_entry(date, added, changed, removed):
    L = [f"## {date}", ""]
    if added:
        L += ["**Neu**", "", "| Spiel | PPSA | Region | Status | Format | Tester | Hinweis |", "|---|---|---|---|---|---|---|"]
        L += [f"| {esc(g['title'])} | {g['ppsa']} | {g['region']} | {STATUS_DE[g['status']]} | {g['format']} | {esc(g['tester'])} | {esc(g['notes'])} |" for g in added]
        L.append("")
    if changed:
        L += ["**Geändert**", "", "| Spiel | Änderung |", "|---|---|"]
        L += [f"| {esc(g['title'])} | {esc(w)} |" for g, w in changed]
        L.append("")
    if removed:
        L += ["**Entfernt**", ""] + [f"- {o['title']}" for o in removed] + [""]
    return "\n".join(L)


def counts(games):
    return {k: sum(1 for g in games if g["status"] == k) for k in STATUS_ORDER}


def write_pdf(games, marks, date, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    cell = ParagraphStyle("c", parent=ss["Normal"], fontSize=7.5, leading=9)
    head = ParagraphStyle("h", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    esc_x = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    c = counts(games)
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=10 * mm, bottomMargin=12 * mm,
                            title="PS5 ZSTD-Kompatibilitätsliste", author="Community-Datenbank (CC BY 4.0)")
    el = [Paragraph("PS5 ZSTD-Kompatibilitätsliste", ss["Title"]),
          Paragraph(f"Stand: {date} · {len(games)} Spiele · " + " · ".join(f"{STATUS_DE[k]}: {c[k]}" for k in STATUS_ORDER), ss["Normal"]),
          Paragraph("Quelle: PS5 ZSTD Compatibility Database (theweil.github.io/PS5-ZSTD-Compatibility), "
                    "Lizenz CC BY 4.0. Hinweise aus dem Chinesischen übersetzt; Tester-Nicknames im Original.", cell)]
    if marks:
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(f"<b>Seit der letzten Aktualisierung:</b> {sum(1 for v in marks.values() if v == 'NEU')} neu, "
                            f"{sum(1 for v in marks.values() if v == 'GEÄNDERT')} geändert (blau hinterlegt).", ss["Normal"]))
    el.append(Spacer(1, 4 * mm))
    data = [[Paragraph(h, head) for h in ("Nr.", "Spiel", "PPSA", "Region", "Status", "Format", "Tester", "Hinweise")]]
    colors_st = {"ok": "#1b7f3b", "fail": "#b3261e", "mixed": "#b26a00", "unknown": "#555555"}
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb")),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")])]
    for i, g in enumerate(games, 1):
        m = marks.get(g["id"])
        title = esc_x(g["title"]) + (f" <b>[{m}]</b>" if m else "")
        data.append([Paragraph(str(i), cell), Paragraph(title, cell), Paragraph(esc_x(g["ppsa"]), cell),
                     Paragraph(esc_x(g["region"]), cell),
                     Paragraph(f'<font color="{colors_st[g["status"]]}"><b>{STATUS_DE[g["status"]]}</b></font>', cell),
                     Paragraph(esc_x(g["format"]), cell), Paragraph(esc_x(g["tester"]), cell),
                     Paragraph(esc_x(g["notes"]), cell)])
        if m:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#dce9ff")))
    t = Table(data, colWidths=[9 * mm, 52 * mm, 30 * mm, 14 * mm, 22 * mm, 14 * mm, 35 * mm, 101 * mm], repeatRows=1)
    t.setStyle(TableStyle(style))
    el.append(t)

    def footer(cv, d):
        cv.setFont("Helvetica", 7)
        cv.drawRightString(landscape(A4)[0] - 10 * mm, 6 * mm, f"Seite {d.page}")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)


def write_readme(games, date):
    c = counts(games)
    rows = "\n".join(f"| {STATUS_DE[k]} | {c[k]} |" for k in STATUS_ORDER)
    (ROOT / "README.md").write_text(f"""# PS5 ZSTD-Kompatibilitätsliste (Deutsch)

Deutsche Übersicht, welche PS5-Spiele als ZSTD- oder LZ4-komprimiertes Backup (z. B. `.ffpfsc`) laufen.
Die Liste wird täglich automatisch aktualisiert.

## Download

**[⬇ Aktuelle PDF herunterladen](https://github.com/strongt1me/ps5-zstd-kompatibilitaetsliste/releases/latest/download/{PDF_NAME})**

Was neu ist, steht im [CHANGELOG](CHANGELOG.md). In der PDF sind neue und geänderte Spiele mit
`[NEU]` bzw. `[GEÄNDERT]` markiert und blau hinterlegt.

## Stand: {date}

{len(games)} Spiele

| Status | Anzahl |
|---|---|
{rows}

- **Läuft**: alle Testberichte erfolgreich
- **Läuft nicht**: alle Testberichte fehlgeschlagen
- **Widersprüchlich**: Berichte mit unterschiedlichem Ergebnis
- **Unbestätigt**: Ergebnis unklar

## Was ist ZSTD?

Zstandard (ZSTD) ist ein verlustfreies Kompressionsverfahren (Yann Collet, Meta, Open Source). Es komprimiert
ähnlich gut wie zlib, entpackt aber viel schneller. LZ4 stammt vom selben Entwickler, entpackt noch schneller,
komprimiert aber schwächer.

## Quelle und Lizenz

Daten: [PS5 ZSTD Compatibility Database](https://theweil.github.io/PS5-ZSTD-Compatibility/)
([GitHub](https://github.com/Theweil/PS5-ZSTD-Compatibility)), Lizenz CC BY 4.0. Hinweise wurden aus dem
Chinesischen übersetzt; Tester-Nicknames stehen im Original. Eigene Ergänzungen stehen in
`data/manual.json` (z. B. Gothic 1 Remake, Test von muxi), bis die Quelle sie führt.
Chinesische Hinweise, die noch keine Übersetzung in `data/translations.json` haben, werden ausgelassen.

Gebaut mit `python build.py` (benötigt `reportlab`).
""", encoding="utf-8")


def main():
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    games = build_games()
    state_path = ROOT / "state.json"
    first = not state_path.exists()
    old = {} if first else {g["id"]: g for g in json.loads(state_path.read_text(encoding="utf-8"))["games"]}
    added, changed, removed = diff(old, games) if not first else ([], [], [])
    marks = {g["id"]: "NEU" for g in added}
    marks.update({g["id"]: "GEÄNDERT" for g, _ in changed})
    print(f"{len(games)} Spiele, neu: {len(added)}, geändert: {len(changed)}, entfernt: {len(removed)}")
    if DRY:
        print(changelog_entry(date, added, changed, removed) if (added or changed or removed) else "keine Änderungen")
        return
    if not first and not (added or changed or removed):
        # Keine Aenderung: nichts neu veroeffentlichen, PDF trotzdem (ohne Markierungen) lokal verfuegbar halten
        if not (ROOT / PDF_NAME).exists():
            write_pdf(games, {}, date, ROOT / PDF_NAME)
        print("keine Änderungen")
        return
    # PDF mit Markierungen der letzten Aenderung
    write_pdf(games, marks, date, ROOT / PDF_NAME)
    cl = ROOT / "CHANGELOG.md"
    header = "# Changelog\n\nNeue und geänderte Einträge pro Aktualisierung (neueste zuerst).\n\n"
    body = cl.read_text(encoding="utf-8").split("\n\n", 2)[2] if cl.exists() else ""
    if not first:
        body = changelog_entry(date, added, changed, removed) + "\n" + body
    cl.write_text(header + body, encoding="utf-8")
    state_path.write_text(json.dumps({"date": date, "games": games}, ensure_ascii=False, indent=1), encoding="utf-8")
    write_readme(games, date)
    (ROOT / ".changed").write_text(date)
    print("PDF, CHANGELOG, README, state.json geschrieben")


if __name__ == "__main__":
    main()
