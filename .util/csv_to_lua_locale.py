#!/usr/bin/env python3
"""Generate LibBabble locale tables from selected WoW CSV exports.

The English and localized rows are matched by table and record ID. WMOAreaTable
uses the same ID/name matching even though its columns are ordered differently.
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
import re


CLIENT_BUILDS = {
    "Mainline": "12.1.5.70783",
    "ClassicEra": "1.15.9.70576",
    "ClassicTBC": "2.5.6.70577",
    "ClassicForever": "1.60.1.70862",
    "ClassicProgression": "5.5.4.70631",
}

LOCALES = (
    "deDE",
    "enUS",
    "esES",
    "esMX",
    "frFR",
    "itIT",
    "koKR",
    "ptBR",
    "ruRU",
    "zhCN",
    "zhTW",
)
TABLES = (
    ("AreaTable", "AreaName_lang"),
    ("JournalInstance", "Name_lang"),
    ("LFGDungeons", "Name_lang"),
    ("Map", "MapName_lang"),
    ("TaxiNodes", "Name_lang"),
    ("UiMap", "Name_lang"),
    ("WMOAreaTable", "AreaName_lang"),
)
BLACKLIST_PATTERNS = (
    r"unused",
    r"do not use",
    r"do not disturb",
    r"don't use",
    r"deprecated",
    r"\[DNT\]",
    r"\[HIDDEN\]",
    r"\[NOT USED\]",
    r"\[PH\]",
    r"\[PL\]",
    r"\[TEMP\]",
    r"\[TEST\]",
    r"^<unnamed poi\s+\d+>$",
    r"^<unused>",
    r"^(?:xxold|zzold)",
    r"(?:^|[\s_-])test(?:ing)?(?:$|[\s_-])",
    r"^\d+test\d*$",
    r"^Reuse",
    r"^Quest ",
    r"test$",
    r"^Transport:",
    r"^Torghast:",
    r"^Torghast - ",
)
BLACKLIST = tuple(re.compile(pattern, re.IGNORECASE) for pattern in BLACKLIST_PATTERNS)


def is_blacklisted(name):
    return any(pattern.search(name) for pattern in BLACKLIST)


def normalize_name(name, table, locale):
    if table != "TaxiNodes":
        return name
    separator = "，" if locale in ("zhCN", "zhTW") else " - " if locale == "koKR" else ","
    return name.split(separator, 1)[0].strip()


def read_records(path, name_column, table, locale, filter_names=True):
    records = {}
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        missing = [column for column in ("ID", name_column) if column not in headers]
        if missing:
            raise ValueError("%s is missing: %s" % (path, ", ".join(missing)))

        for row_number, row in enumerate(reader, start=2):
            record_id = (row.get("ID") or "").strip()
            name = (row.get(name_column) or "").strip()
            if not record_id or not name or "NOTUSED" in name.upper():
                continue
            name = normalize_name(name, table, locale)
            if not name:
                continue
            if filter_names and is_blacklisted(name):
                continue
            try:
                record_id = int(record_id)
            except ValueError as error:
                raise ValueError("%s:%d has an invalid ID: %r" % (path, row_number, record_id)) from error
            records[record_id] = name
    return records


def collect_candidates(data_root):
    candidates = {locale: defaultdict(list) for locale in LOCALES}
    english_names = set()

    for client, build in CLIENT_BUILDS.items():
        build_root = data_root / build
        for table, name_column in TABLES:
            english_path = build_root / ("%s.%s_enUS.csv" % (table, build))
            if not english_path.exists():
                continue
            english_records = read_records(english_path, name_column, table, "enUS")
            english_names.update(english_records.values())

            localized_records = {}
            for locale in LOCALES:
                localized_path = build_root / ("%s.%s_%s.csv" % (table, build, locale))
                localized_records[locale] = (
                    read_records(localized_path, name_column, table, locale, filter_names=False)
                    if localized_path.exists()
                    else {}
                )
            for record_id, english_name in english_records.items():
                for locale, records in localized_records.items():
                    localized_name = records.get(record_id)
                    if localized_name:
                        candidates[locale][english_name].append(localized_name)

    return english_names, candidates


def choose_translations(english_names, candidates):
    translations = {}
    for english_name in sorted(english_names):
        values = candidates.get(english_name, [])
        # A client without this locale returns the English text (for example,
        # Classic clients have no itIT), so prefer real translations when any exist.
        translated = [value for value in values if value != english_name]
        if translated:
            values = translated
        if values:
            translations[english_name] = Counter(values).most_common(1)[0][0]
    return translations


def escape_lua_string(value):
    escaped = []
    for character in value:
        codepoint = ord(character)
        if character == "\\":
            escaped.append("\\\\")
        elif character == '"':
            escaped.append('\\"')
        elif character == "\n":
            escaped.append("\\n")
        elif character == "\r":
            escaped.append("\\r")
        elif character == "\t":
            escaped.append("\\t")
        elif codepoint < 32 or codepoint == 127:
            escaped.append("\\%03d" % codepoint)
        else:
            escaped.append(character)
    return "".join(escaped)


def write_locale(path, locale, english_names, translations):
    lines = [
        "-- Generated from selected WoW CSV exports; do not edit manually.",
        "",
        "local _, private = ...",
        "local lib = private[\"LibBabble-SubZone-3.0-LoadingLib\"]",
    ]
    if locale == "enUS":
        lines.append("if not lib then return end")
        lines.append("lib:SetBaseTranslations")
    else:
        lines.append('if not lib or GetLocale() ~= "%s" then return end' % locale)
        lines.append("lib:SetCurrentTranslations")
    lines.extend(["{",])
    for english_name in sorted(english_names):
        localized_name = english_name if locale == "enUS" else translations.get(english_name)
        if localized_name:
            lines.append(
                '\t["%s"] = "%s",'
                % (escape_lua_string(english_name), escape_lua_string(localized_name))
            )
    lines.extend(["}", ""])
    if locale == "enUS":
        lines.extend(["if GetLocale() == \"enUS\" then", "\tlib:SetCurrentTranslations(true)", "end", ""])
    path.write_text("\r\n".join(lines), encoding="utf-8", newline="")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(".data"))
    parser.add_argument("--output-root", type=Path, default=Path("Locale"))
    parser.add_argument("--locale", choices=LOCALES, help="generate only one locale")
    parser.add_argument("--output", type=Path, help="output path when generating one locale")
    arguments = parser.parse_args()

    english_names, candidates = collect_candidates(arguments.data_root)
    if arguments.output and not arguments.locale:
        parser.error("--output requires --locale")
    locales = (arguments.locale,) if arguments.locale else LOCALES
    for locale in locales:
        translations = choose_translations(english_names, candidates[locale])
        output_path = arguments.output if arguments.locale else arguments.output_root / (locale + ".lua")
        write_locale(
            output_path,
            locale,
            english_names,
            translations,
        )
        print("Wrote %s (%d entries)" % (locale, len(translations) if locale != "enUS" else len(english_names)))


if __name__ == "__main__":
    main()