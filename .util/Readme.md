# Maintenance Tools

These scripts maintain the generated data files. They are not needed by addon users, and `.data/` is excluded from packaged releases.

## Supported Builds

The current build mapping is defined in both scripts:

- Mainline: `12.1.5.70783`
- Classic Era: `1.15.9.70576`
- Classic TBC: `2.5.6.70577`
- Classic Forever: `"1.60.1.70862`
- Classic Progression: `5.5.4.70631`

Update the mapping when a new client build becomes the source of truth.

## Download CSV Data

Preview the full download plan:

```text
python .util/download_wago_tables.py --dry-run
```

Download all supported tables, clients, and locales:

```text
python .util/download_wago_tables.py
```

The default batch is 5 builds x 11 locales x 7 tables. The supported tables are:

- `AreaTable`
- `JournalInstance`
- `LFGDungeons`
- `Map`
- `TaxiNodes`
- `UiMap`
- `WMOAreaTable`

For a focused update, for example all WMO data:

```text
python .util/download_wago_tables.py --tables WMOAreaTable
```

For only Mainline English data:

```text
python .util/download_wago_tables.py --clients Mainline --locales enUS
```

Use `--tables`, `--clients`, `--locales`, `--limit`, `--delay`, `--retries`, and `--overwrite` to control the batch. Existing files are skipped unless `--overwrite` is supplied. Responses are checked for required columns before being saved.

WMOAreaTable has `AreaName_lang` before `ID`; the downloader validates columns by name, so column order does not matter.

## Generate API Indexes

Generate both legacy compatibility maps and candidate-ID indexes for all clients:

```text
python .util/csv_to_lua_area_table.py --all
```

The files are written to `Data/`:

- `Data/AreaToUIMapID_<client>.lua`
- `Data/LocalizedNameIndexes_<client>.lua`

The compatibility map stores the first sorted AreaTable ID for duplicate names. The candidate index stores every matching AreaTable or UiMap ID and is used by the runtime resolver.

For one client from explicit CSV paths:

```text
python .util/csv_to_lua_area_table.py \
  .data/12.1.5.69952/AreaTable.12.1.5.69952_enUS.csv \
  --ui-map .data/12.1.5.69952/UiMap.12.1.5.69952_enUS.csv \
  --client Mainline \
  --output Data/LocalizedNameIndexes_Mainline.lua \
  --area-output Data/AreaToUIMapID_Mainline.lua
```

## Generate Locale Tables

Generate all shipped locales from the current CSV data:

```text
python .util/csv_to_lua_locale.py
```

Generate one comparison file without replacing the shipped locale:

```text
python .util/csv_to_lua_locale.py \
  --locale enUS \
  --output Locale/enUS_test.lua
```

The locale merge matches English and localized rows by table and record ID. It includes `AreaTable`, `JournalInstance`, `LFGDungeons`, `Map`, `TaxiNodes`, `UiMap`, and `WMOAreaTable`.

TaxiNodes names are normalized to the node name before merging:

- Most locales: text before `,`
- Korean: text before ` - `
- Simplified and Traditional Chinese: text before `，`

WMOAreaTable names are matched by `AreaName_lang` and `ID`, regardless of column order. Empty names and records containing `NOTUSED` are ignored.

## Blacklist

The locale generator filters English names matching the blacklist before adding them to the base locale. The current patterns cover:

- Unused, deprecated, do-not-use, hidden, DNT, PH, and temporary records
- Unnamed POI records
- `xxOLD` and `zzOLD` records
- Explicit test names, including names containing a standalone `Test`, numeric test names such as `11Test1`, and names ending in `test`

The blacklist is applied only to English source names. Localized rows are still read by record ID, so a translation is not discarded merely because its translated text contains one of these words.

Edit `BLACKLIST_PATTERNS` in `csv_to_lua_locale.py` when the source data exposes another class of invalid records. Regenerate the locale files after changing it.

## Validation

After regeneration, run:

```text
python -m py_compile .util/download_wago_tables.py .util/csv_to_lua_area_table.py .util/csv_to_lua_locale.py
```

Check that:

- Every generated client file is listed in `lib.xml`.
- `AreaToUIMapID_<client>.lua` loads before `LocalizedNameIndexes_<client>.lua`.
- Generated locale files do not contain blacklisted names.
- A representative TaxiNodes name uses only the node portion, such as `Glitterfall Basin` instead of `Glitterfall Basin, Ardenweald`.
- WMO-derived names appear in the generated locale output.

The generated Lua files and locale tables are the shipped artifacts; the CSV files remain maintenance inputs only.
