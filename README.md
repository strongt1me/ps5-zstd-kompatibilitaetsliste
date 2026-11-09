# PS5 ZSTD-Kompatibilitätsliste (Deutsch)

Deutsche Übersicht, welche PS5-Spiele als ZSTD- oder LZ4-komprimiertes Backup (z. B. `.ffpfsc`) laufen.
Die Liste wird täglich automatisch aktualisiert.

## Download

**[⬇ Aktuelle PDF herunterladen](https://github.com/strongt1me/ps5-zstd-kompatibilitaetsliste/releases/latest/download/PS5-ZSTD-Kompatibilitaetsliste.pdf)**

Was neu ist, steht im [CHANGELOG](CHANGELOG.md). In der PDF sind neue und geänderte Spiele mit
`[NEU]` bzw. `[GEÄNDERT]` markiert und blau hinterlegt.

## Stand: 2026-11-09

94 Spiele

| Status | Anzahl |
|---|---|
| Läuft | 83 |
| Läuft nicht | 7 |
| Widersprüchlich | 3 |
| Unbestätigt | 1 |

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
