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
PDF_NAME = "PS5-ZSTD-LZ4-Kompatibilitaetsliste.pdf"
PDF_NAME_EN = "PS5-ZSTD-LZ4-Compatibility-List.pdf"
DRY = "--dry-run" in sys.argv

STATUS_DE = {"ok": "Läuft", "fail": "Läuft nicht", "mixed": "Widersprüchlich", "unknown": "Unbestätigt"}
STATUS_EN = {"ok": "Works", "fail": "Does not run", "mixed": "Conflicting", "unknown": "Unconfirmed"}
UI = {
    "de": {"title": "PS5 ZSTD &amp; LZ4 Kompatibilitätsliste", "meta": "Stand", "games": "Spiele", "status": STATUS_DE,
           "src": "Quelle: PS5 ZSTD Compatibility Database (theweil.github.io/PS5-ZSTD-Compatibility), Lizenz CC BY 4.0. Hinweise aus dem Chinesischen übersetzt; Tester-Nicknames im Original.",
           "since": "Seit der letzten Aktualisierung:", "new": "neu", "chg": "geändert", "blue": "blau hinterlegt",
           "mnew": "NEU", "mchg": "GEÄNDERT", "page": "Seite", "tested": "getestet am", "date": "%d.%m.%Y",
           "cols": ("Nr.", "Spiel", "PPSA", "Region", "Status", "Format", "Tester", "Hinweise")},
    "en": {"title": "PS5 ZSTD &amp; LZ4 Compatibility List", "meta": "As of", "games": "games", "status": STATUS_EN,
           "src": "Source: PS5 ZSTD Compatibility Database (theweil.github.io/PS5-ZSTD-Compatibility), licence CC BY 4.0. Notes translated from Chinese; tester nicknames as in the original.",
           "since": "Since the last update:", "new": "new", "chg": "changed", "blue": "highlighted in blue",
           "mnew": "NEW", "mchg": "CHANGED", "page": "Page", "tested": "tested on", "date": "%Y-%m-%d",
           "cols": ("No.", "Game", "PPSA", "Region", "Status", "Format", "Tester", "Notes")},
}
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
        return f"Version {v}" + (f" / {size} GB" if size else "") + (f" ({who})" if who else "")
    if CJK.search(note):
        print(f"WARNUNG: Hinweis nicht übersetzt, wird ausgelassen: {note!r}", file=sys.stderr)
        return None
    return note


def build_games(lang="de"):
    games = fetch("games.json")["games"]
    tests = fetch("tests.json")["tests"]
    tr = load_json(ROOT / "data" / ("translations.json" if lang == "de" else "translations_en.json"), {})
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
            r["notes"].append(f"{UI[lang]['tested']} {datetime.fromisoformat(t['tested_at']).strftime(UI[lang]['date'])}")

    # eigene, manuell gepflegte Eintraege (falls die Quelle sie noch nicht hat)
    have = " ".join(r["title"].lower() for r in rows.values())
    for m in manual:
        notes = m["notes"][lang] if isinstance(m["notes"], dict) else m["notes"]
        if m.get("extra_for"):  # zusaetzlicher Testbericht zu einem Spiel, das die Quelle schon fuehrt
            r = rows.get(m["extra_for"])
            if r is None:
                continue
            for key, vals in (("ppsa", m["ppsa"]), ("regions", m["regions"]), ("formats", m["formats"]),
                              ("testers", m["testers"]), ("notes", notes)):
                r[key] += [v for v in vals if v not in r[key]]
            r["results"] += m["results"]
            continue
        if m["match"].lower() in have:
            continue
        rows[m["id"]] = {"id": m["id"], "title": m["title"], "ppsa": m["ppsa"], "regions": m["regions"],
                         "results": m["results"], "formats": m["formats"], "testers": m["testers"],
                         "notes": notes}

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
                what.append(("status", o["status"], g["status"], []))
            if o["format"] != g["format"]:
                what.append(("format", o["format"], g["format"], []))
            if o["tests"] != g["tests"]:
                what.append(("tests", o["tests"], g["tests"], [t for t in g["tester"].split(", ") if t not in o["tester"]],
                         [x for x in g["notes"].split("; ") if x and x not in o["notes"]]))
            if what:
                changed.append((g, what))
    removed = [o for i, o in old.items() if i not in {g['id'] for g in new}]
    return added, changed, removed


def esc(s):
    return s.replace("|", "\\|")


CL = {
    "de": {"head": "# Changelog\n\nNeue und geänderte Einträge pro Aktualisierung (neueste zuerst).\n\n",
           "new": "**Neu**", "chg": "**Geändert**", "rem": "**Entfernt**", "game": "Spiel", "change": "Änderung",
           "cols": "| Spiel | PPSA | Region | Status | Format | Tester | Hinweis |", "status": STATUS_DE,
           "format": "Format", "tests": "Testberichte", "newfrom": "neu von"},
    "en": {"head": "# Changelog\n\nNew and changed entries per update (newest first).\n\n",
           "new": "**New**", "chg": "**Changed**", "rem": "**Removed**", "game": "Game", "change": "Change",
           "cols": "| Game | PPSA | Region | Status | Format | Tester | Note |", "status": STATUS_EN,
           "format": "Format", "tests": "Test reports", "newfrom": "new from"},
}


def changelog_entry(date, added, changed, removed, lang="de", rows=None):
    """rows: id -> Spielzeile in der Zielsprache (fuer uebersetzte Hinweise)."""
    C = CL[lang]
    rows = rows or {}
    L = [f"## {date}", ""]
    if added:
        L += [C["new"], "", C["cols"], "|---|---|---|---|---|---|---|"]
        for g in added:
            g = rows.get(g["id"], g)
            L.append(f"| {esc(g['title'])} | {g['ppsa']} | {g['region']} | {C['status'][g['status']]} | {g['format']} | {esc(g['tester'])} | {esc(g['notes'])} |")
        L.append("")
    if changed:
        L += [C["chg"], "", f"| {C['game']} | {C['change']} |", "|---|---|"]
        for g, what in changed:
            parts = []
            for k, o, n, *extra in what:
                if k == "status":
                    parts.append(f"Status: {C['status'][o]} → {C['status'][n]}")
                elif k == "tests" and extra and extra[0]:
                    det = ": " + "; ".join(extra[1]) if len(extra) > 1 and extra[1] else ""
                    parts.append(f"{C[k]}: {o} → {n} ({C['newfrom']} {', '.join(extra[0])}){det}")
                else:
                    parts.append(f"{C[k]}: {o} → {n}")
            L.append(f"| {esc(g['title'])} | {esc('; '.join(parts))} |")
        L.append("")
    if removed:
        L += [C["rem"], ""] + [f"- {o['title']}" for o in removed] + [""]
    return "\n".join(L)


def counts(games):
    return {k: sum(1 for g in games if g["status"] == k) for k in STATUS_ORDER}


def write_pdf(games, marks, date, path, lang="de"):
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
    U = UI[lang]
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=10 * mm, bottomMargin=12 * mm,
                            title=U["title"].replace("&amp;", "&"), author="Community-Datenbank (CC BY 4.0)")
    el = [Paragraph(U["title"], ss["Title"]),
          Paragraph(f"{U['meta']}: {date} · {len(games)} {U['games']} · " + " · ".join(f"{U['status'][k]}: {c[k]}" for k in STATUS_ORDER), ss["Normal"]),
          Paragraph(U["src"], cell)]
    if marks:
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(f"<b>{U['since']}</b> {sum(1 for v in marks.values() if v == 'NEU')} {U['new']}, "
                            f"{sum(1 for v in marks.values() if v == 'GEÄNDERT')} {U['chg']} ({U['blue']}).", ss["Normal"]))
    el.append(Spacer(1, 4 * mm))
    data = [[Paragraph(h, head) for h in U["cols"]]]
    colors_st = {"ok": "#1b7f3b", "fail": "#b3261e", "mixed": "#b26a00", "unknown": "#555555"}
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb")),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")])]
    for i, g in enumerate(games, 1):
        m = marks.get(g["id"])
        title = esc_x(g["title"]) + (f" <b>[{U['mnew'] if m == 'NEU' else U['mchg']}]</b>" if m else "")
        data.append([Paragraph(str(i), cell), Paragraph(title, cell), Paragraph(esc_x(g["ppsa"]), cell),
                     Paragraph(esc_x(g["region"]), cell),
                     Paragraph(f'<font color="{colors_st[g["status"]]}"><b>{U["status"][g["status"]]}</b></font>', cell),
                     Paragraph(esc_x(g["format"]), cell), Paragraph(esc_x(g["tester"]), cell),
                     Paragraph(esc_x(g["notes"]), cell)])
        if m:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#dce9ff")))
    t = Table(data, colWidths=[9 * mm, 52 * mm, 30 * mm, 14 * mm, 22 * mm, 14 * mm, 35 * mm, 101 * mm], repeatRows=1)
    t.setStyle(TableStyle(style))
    el.append(t)

    def footer(cv, d):
        cv.setFont("Helvetica", 7)
        cv.drawRightString(landscape(A4)[0] - 10 * mm, 6 * mm, f"{U['page']} {d.page}")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)


README_DE = """![PS5 ZSTD & LZ4 Kompatibilitätsliste](banner.png)

# PS5 ZSTD & LZ4 Kompatibilitätsliste (Deutsch)

**Deutsch** | [English](README.en.md)

Deutsche Übersicht, welche PS5-Spiele als ZSTD- oder LZ4-komprimiertes Backup (z. B. `.ffpfsc`) laufen.
Die Liste wird täglich automatisch aktualisiert.

## Download

**[⬇ Aktuelle PDF herunterladen (Deutsch)](https://github.com/strongt1me/ps5-zstd-kompatibilitaetsliste/releases/latest/download/{pdf_de})**
· **[⬇ Download latest PDF (English)](https://github.com/strongt1me/ps5-zstd-kompatibilitaetsliste/releases/latest/download/{pdf_en})**

Was neu ist, steht im [CHANGELOG](CHANGELOG.md). In der PDF sind neue und geänderte Spiele mit
`[NEU]` bzw. `[GEÄNDERT]` markiert und blau hinterlegt.

## Stand: {date}

{n} Spiele

| Status | Anzahl |
|---|---|
{rows}

- **Läuft**: alle Testberichte erfolgreich
- **Läuft nicht**: alle Testberichte fehlgeschlagen
- **Widersprüchlich**: Berichte mit unterschiedlichem Ergebnis
- **Unbestätigt**: Ergebnis unklar

## Was ist ZSTD?

Zstandard (ZSTD) ist ein verlustfreies Kompressionsverfahren, entwickelt von Yann Collet bei Facebook (heute Meta)
und seit 2016 Open Source. Es komprimiert ähnlich gut wie zlib/gzip, entpackt aber deutlich schneller. Das ist
ideal, wenn Daten zur Laufzeit entpackt werden.

## Was ist LZ4?

LZ4 ist ebenfalls ein verlustfreies Kompressionsverfahren und stammt vom selben Entwickler (Yann Collet).
Es ist auf maximale Geschwindigkeit ausgelegt: LZ4 entpackt noch schneller als ZSTD, komprimiert aber
schwächer, die Dateien werden also größer.

## Warum ist das für die PS5 wichtig?

Spiel-Backups werden mit ZSTD oder LZ4 komprimiert, damit sie weniger Speicherplatz brauchen (z. B. als
`.ffpfsc`). Beim Spielen entpackt ein Emulator für die AMPR-Schnittstelle (ampr-emu bzw. libSceAmpr) die Daten
in Echtzeit. Die Liste zeigt, welche Spiele in dieser komprimierten Form tatsächlich laufen. In der Spalte
„Format“ steht, mit welchem Verfahren getestet wurde.

## Hinweis zu den Tests von muxi

muxi packt alle Titel grundsätzlich im exFAT-Image-Format. Das spielt für die Funktion eines Titels zwar keine Rolle,
ist aber erwähnenswert.

## Quelle und Lizenz

Daten: [PS5 ZSTD Compatibility Database](https://theweil.github.io/PS5-ZSTD-Compatibility/)
([GitHub](https://github.com/Theweil/PS5-ZSTD-Compatibility)), Lizenz CC BY 4.0. Hinweise wurden aus dem
Chinesischen übersetzt; Tester-Nicknames stehen im Original. Eigene Ergänzungen stehen in
`data/manual.json` (z. B. Gothic 1 Remake, Test von muxi), bis die Quelle sie führt.
Chinesische Hinweise, die noch keine Übersetzung in `data/translations.json` haben, werden ausgelassen.

Gebaut mit `python build.py` (benötigt `reportlab`).
"""


README_EN = """![PS5 ZSTD & LZ4 Compatibility List](banner.png)

# PS5 ZSTD & LZ4 Compatibility List (English)

[Deutsch](README.md) | **English**

Overview of which PS5 games run as ZSTD- or LZ4-compressed backups (e.g. `.ffpfsc`).
The list is updated automatically every day.

## Download

**[⬇ Download latest PDF (English)](https://github.com/strongt1me/ps5-zstd-kompatibilitaetsliste/releases/latest/download/{pdf_en})**
· **[⬇ Aktuelle PDF (Deutsch)](https://github.com/strongt1me/ps5-zstd-kompatibilitaetsliste/releases/latest/download/{pdf_de})**

See the [CHANGELOG](CHANGELOG.en.md) for what is new. In the PDF, new and changed games are marked
`[NEW]` / `[CHANGED]` and highlighted in blue.

## Status: {date}

{n} games

| Status | Count |
|---|---|
{rows}

- **Works**: all test reports successful
- **Does not run**: all test reports failed
- **Conflicting**: reports with different results
- **Unconfirmed**: result unclear

## What is ZSTD?

Zstandard (ZSTD) is a lossless compression algorithm developed by Yann Collet at Facebook (now Meta) and open
source since 2016. It compresses about as well as zlib/gzip but decompresses much faster, which is ideal when
data is unpacked at runtime.

## What is LZ4?

LZ4 is also a lossless compression algorithm by the same author (Yann Collet). It is built for maximum speed:
LZ4 decompresses even faster than ZSTD but compresses less, so the files end up larger.

## Why does this matter for the PS5?

Game backups are compressed with ZSTD or LZ4 to save disk space (e.g. as `.ffpfsc`). While playing, an emulator
for the AMPR interface (ampr-emu / libSceAmpr) decompresses the data in real time. This list shows which games
actually run in this compressed form. The "Format" column states which algorithm was used for the test.

## Note on muxi's tests

muxi packs all titles as exFAT images. This should not matter for whether a title works, but it is worth mentioning.

## Source and licence

Data: [PS5 ZSTD Compatibility Database](https://theweil.github.io/PS5-ZSTD-Compatibility/)
([GitHub](https://github.com/Theweil/PS5-ZSTD-Compatibility)), licence CC BY 4.0. Notes were translated from
Chinese; tester nicknames are as in the original. Own additions are in `data/manual.json` (e.g. Gothic 1 Remake,
tested by muxi) until the source lists them. Chinese notes without a translation in `data/translations_en.json`
are omitted.

Built with `python build.py` (requires `reportlab`).
"""


BANNER = ROOT / "banner.png"
BANNER_COLORS = {"ok": (80, 200, 120), "fail": (235, 90, 90), "mixed": (240, 190, 60), "unknown": (160, 170, 190)}


def write_banner(games, date):
    """Forum-/Header-Bild mit den aktuellen Zahlen (passt zum jeweils letzten Release)."""
    from PIL import Image, ImageDraw, ImageFont

    def font(size, bold=True):
        names = (["segoeuib.ttf", "DejaVuSans-Bold.ttf"] if bold else ["segoeui.ttf", "DejaVuSans.ttf"])
        for n in names:
            for base in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/"):
                try:
                    return ImageFont.truetype(base + n, size)
                except OSError:
                    pass
        return ImageFont.load_default()

    W, H = 1200, 500
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(8 + 10 * t), int(20 + 40 * t), int(60 + 70 * t)))
    d.rectangle([0, 0, 14, H], fill=(0, 112, 209))
    d.text((70, 60), "PS5  ZSTD & LZ4", font=font(88), fill="white")
    d.text((70, 170), "Kompatibilitätsliste", font=font(60), fill=(120, 190, 255))
    d.text((70, 255), "Welche PS5-Spiele laufen als komprimiertes Backup (.ffpfsc)?", font=font(30, False), fill=(210, 220, 235))
    c = counts(games)
    boxes = [(str(len(games)), "Spiele", (230, 230, 230))]
    boxes += [(str(c[k]), STATUS_DE[k], BANNER_COLORS.get(k, (200, 200, 200))) for k in STATUS_ORDER if c[k]]
    x = 70
    gap = 20
    bw = (W - 70 - 60 - gap * (len(boxes) - 1)) // len(boxes)
    for n, label, col in boxes:
        d.rounded_rectangle([x, 340, x + bw, 450], 14, fill=(20, 40, 80), outline=col, width=3)
        d.text((x + 20, 345), n, font=font(56), fill=col)
        d.text((x + 20, 412), label, font=font(22, False), fill=(210, 220, 235))
        x += bw + gap
    d.text((70, 462), f"Stand: {date} · täglich aktualisiert · Deutsch & English", font=font(20, False), fill=(150, 170, 200))
    img.save(BANNER)


def write_readme(games, date):
    c = counts(games)
    rows = "\n".join(f"| {STATUS_DE[k]} | {c[k]} |" for k in STATUS_ORDER)
    rows_en = "\n".join(f"| {STATUS_EN[k]} | {c[k]} |" for k in STATUS_ORDER)
    (ROOT / "README.en.md").write_text(README_EN.format(pdf_en=PDF_NAME_EN, pdf_de=PDF_NAME, date=date,
                                                       n=len(games), rows=rows_en), encoding="utf-8")
    (ROOT / "README.md").write_text(README_DE.format(pdf_de=PDF_NAME, pdf_en=PDF_NAME_EN, date=date,
                                                    n=len(games), rows=rows), encoding="utf-8")


def main():
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    games = build_games()
    games_en = build_games("en")
    rows_en = {g["id"]: g for g in games_en}
    state_path = ROOT / "state.json"
    first = not state_path.exists()
    st = {} if first else json.loads(state_path.read_text(encoding="utf-8"))
    old = {g["id"]: g for g in st.get("games", [])}
    if "games_en" in st:
        old_en = {g["id"]: g for g in st["games_en"]}
    else:  # aeltere state.json ohne englische Zeilen: nur Status/Format/Tester/Anzahl vergleichen
        old_en = {i: {**rows_en[i], **{k: o[k] for k in ("status", "format", "tester", "tests")}}
                  for i, o in old.items() if i in rows_en}
    added, changed, removed = diff(old, games) if not first else ([], [], [])
    changed_en = diff(old_en, games_en)[1] if not first else []
    marks = {g["id"]: "NEU" for g in added}
    marks.update({g["id"]: "GEÄNDERT" for g, _ in changed})
    print(f"{len(games)} Spiele, neu: {len(added)}, geändert: {len(changed)}, entfernt: {len(removed)}")
    if DRY:
        print(changelog_entry(date, added, changed, removed) if (added or changed or removed) else "keine Änderungen")
        return
    if not first and not (added or changed or removed):
        # Keine Aenderung: nichts neu veroeffentlichen, fehlende Dateien aber nachbauen
        if not (ROOT / PDF_NAME).exists():
            write_pdf(games, {}, date, ROOT / PDF_NAME)
        if not (ROOT / PDF_NAME_EN).exists():
            write_pdf(games_en, {}, date, ROOT / PDF_NAME_EN, "en")
        if not BANNER.exists():
            write_banner(games, json.loads(state_path.read_text(encoding="utf-8"))["date"])
        print("keine Änderungen")
        return
    write_pdf(games, marks, date, ROOT / PDF_NAME)
    write_pdf(games_en, marks, date, ROOT / PDF_NAME_EN, "en")
    for lang, name in (("de", "CHANGELOG.md"), ("en", "CHANGELOG.en.md")):
        cl = ROOT / name
        body = cl.read_text(encoding="utf-8").split("\n\n", 2)[2] if cl.exists() else ""
        if not first:
            body = changelog_entry(date, added, changed_en if lang == "en" else changed, removed, lang, rows_en if lang == "en" else None) + "\n" + body
        cl.write_text(CL[lang]["head"] + body, encoding="utf-8")
    state_path.write_text(json.dumps({"date": date, "games": games, "games_en": games_en}, ensure_ascii=False, indent=1), encoding="utf-8")
    write_readme(games, date)
    write_banner(games, date)
    (ROOT / ".changed").write_text(date)
    print("PDFs, CHANGELOGs, READMEs, state.json geschrieben")


if __name__ == "__main__":
    main()
