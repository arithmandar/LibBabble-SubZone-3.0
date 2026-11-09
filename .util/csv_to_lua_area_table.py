#!/usr/bin/env python3
"""Generate Lua name-to-candidate-ID indexes from WoW CSV exports.

AreaTable names are indexed for C_Map.GetAreaInfo(areaID). UiMap names are
indexed separately for C_Map.GetMapInfo(uiMapID); the ID domains are distinct.

Example:
    python csv_to_lua_area_table.py AreaTable.csv \\
        --ui-map UiMap.csv --client Mainline \
        --output Data/LocalizedNameIndexes_Mainline.lua

Generate every supported client from the current .data layout:
    python csv_to_lua_area_table.py --all
"""

import argparse
import csv
from collections import defaultdict
import os

CLIENT_BUILDS = {
    "Mainline": "12.1.5.70783",
    "ClassicEra": "1.15.9.70576",
    "ClassicTBC": "2.5.6.70577",
    "ClassicForever": "1.60.1.70862",
    "ClassicProgression": "5.5.4.70631",
}

CLIENT_GUARDS = {
    "Mainline": "if WOW_PROJECT_ID ~= WOW_PROJECT_MAINLINE then return end\n\n",
    "ClassicEra": "if WOW_PROJECT_ID ~= WOW_PROJECT_CLASSIC then return end\n\n",
    "ClassicForever": "if WOW_PROJECT_ID ~= WOW_PROJECT_CAMELOT then return end\n\n",
    "ClassicProgression": (
        "local projectID = WOW_PROJECT_ID\n"
        "local PROJECT_CATA = WOW_PROJECT_CATACLYSM_CLASSIC\n"
        "local PROJECT_MISTS = WOW_PROJECT_MISTS_CLASSIC\n"
        "local isCataclysmClassic = PROJECT_CATA ~= nil and projectID == PROJECT_CATA\n"
        "local isMistsClassic = PROJECT_MISTS ~= nil and projectID == PROJECT_MISTS\n"
        "local isProgressionClassic = isCataclysmClassic or isMistsClassic\n"
        "if not isProgressionClassic then return end\n\n"
    ),
    "ClassicTBC": (
        "local projectID = WOW_PROJECT_ID\n"
        "local PROJECT_TBC = WOW_PROJECT_BURNING_CRUSADE_CLASSIC\n"
        "local isAnniversaryTBC = PROJECT_TBC ~= nil and projectID == PROJECT_TBC\n"
        "if not isAnniversaryTBC then return end\n\n"
    ),
}


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


def read_name_ids(input_path, name_column, id_column="ID"):
    name_ids = defaultdict(set)
    with open(input_path, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        missing_columns = [column for column in (name_column, id_column) if column not in headers]
        if missing_columns:
            raise ValueError(
                "%s is missing required column(s): %s"
                % (input_path, ", ".join(missing_columns))
            )

        for row_number, row in enumerate(reader, start=2):
            name = (row.get(name_column) or "").strip()
            id_value = (row.get(id_column) or "").strip()
            if not name:
                continue
            try:
                record_id = int(id_value)
            except ValueError as error:
                raise ValueError(
                    "%s:%d has an invalid %s: %r"
                    % (input_path, row_number, id_column, id_value)
                ) from error
            name_ids[name].add(record_id)

    return {
        name: sorted(record_ids)
        for name, record_ids in sorted(name_ids.items())
    }


def write_index(lua_file, property_name, name_ids):
    lua_file.write("MapData.%s = {\n" % property_name)
    for name, record_ids in name_ids.items():
        ids = ", ".join(str(record_id) for record_id in record_ids)
        lua_file.write('\t["%s"] = {%s},\n' % (escape_lua_string(name), ids))
    lua_file.write("}\n\n")


def write_area_to_id(lua_file, area_names):
    lua_file.write("MapData.AreaToID = {\n")
    for name, record_ids in area_names.items():
        if record_ids:
            lua_file.write('\t["%s"] = %s,\n' % (escape_lua_string(name), record_ids[0]))
    lua_file.write("}\n\n")


def convert(area_table_path, output_path, ui_map_path=None, client="Mainline", area_output_path=None):
    if client not in CLIENT_GUARDS:
        raise ValueError("Unsupported client: %s" % client)

    area_names = read_name_ids(area_table_path, "AreaName_lang")
    ui_map_names = None
    if ui_map_path:
        ui_map_names = read_name_ids(ui_map_path, "Name_lang")

    output_directory = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_directory, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\r\n") as lua_file:
        lua_file.write("-- Generated for %s from WoW CSV exports; do not edit manually.\n" % client)
        lua_file.write("local _, private = ...\n")
        lua_file.write(CLIENT_GUARDS[client])
        lua_file.write('local lib = private["LibBabble-SubZone-3.0-LoadingLib"]\n')
        lua_file.write("if not lib then return end\n")
        lua_file.write("local MapData = lib.MapData\n")
        lua_file.write("if not MapData then return end\n\n")
        write_index(lua_file, "AreaNameToIDs", area_names)
        if ui_map_names is not None:
            write_index(lua_file, "UiMapNameToIDs", ui_map_names)

    if area_output_path:
        area_output_directory = os.path.dirname(os.path.abspath(area_output_path))
        os.makedirs(area_output_directory, exist_ok=True)
        with open(area_output_path, "w", encoding="utf-8", newline="\r\n") as lua_file:
            lua_file.write("-- Generated for %s from WoW CSV exports; do not edit manually.\n" % client)
            lua_file.write("local _, private = ...\n")
            lua_file.write(CLIENT_GUARDS[client])
            lua_file.write('local lib = private["LibBabble-SubZone-3.0-LoadingLib"]\n')
            lua_file.write("if not lib then return end\n")
            lua_file.write("local MapData = lib.MapData\n")
            lua_file.write("if not MapData then return end\n\n")
            write_area_to_id(lua_file, area_names)

    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("area_table_csv", nargs="?", help="AreaTable CSV with AreaName_lang and ID columns")
    parser.add_argument("--ui-map", help="optional UiMap CSV with Name_lang and ID columns")
    parser.add_argument("--client", choices=sorted(CLIENT_GUARDS), default="Mainline")
    parser.add_argument("--all", action="store_true", help="generate all supported clients from --data-root")
    parser.add_argument("--data-root", default=".data", help="root containing build directories")
    parser.add_argument("--output-root", default="Data", help="directory for generated Lua files")
    parser.add_argument("--output", help="client-specific Lua output path")
    parser.add_argument("--area-output", help="legacy AreaToUIMapID Lua output path")
    arguments = parser.parse_args()

    if arguments.all:
        if arguments.area_table_csv or arguments.ui_map or arguments.output:
            parser.error("--all cannot be combined with a positional CSV, --ui-map, or --output")
        for client, build in CLIENT_BUILDS.items():
            area_table_csv = os.path.join(
                arguments.data_root,
                build,
                "AreaTable.%s_enUS.csv" % build,
            )
            ui_map_csv = os.path.join(
                arguments.data_root,
                build,
                "UiMap.%s_enUS.csv" % build,
            )
            output_path = os.path.join(
                arguments.output_root,
                "LocalizedNameIndexes_%s.lua" % client,
            )
            if not os.path.exists(area_table_csv):
                parser.error("missing AreaTable input: %s" % area_table_csv)
            if not os.path.exists(ui_map_csv):
                parser.error("missing UiMap input: %s" % ui_map_csv)
            area_output_path = os.path.join(
                arguments.output_root,
                "AreaToUIMapID_%s.lua" % client,
            )
            print("Wrote: %s" % convert(area_table_csv, output_path, ui_map_csv, client, area_output_path))
        return

    if not arguments.area_table_csv:
        parser.error("area_table_csv is required unless --all is used")
    output_path = arguments.output or os.path.join(
        arguments.output_root,
        "LocalizedNameIndexes_%s.lua" % arguments.client,
    )
    area_output_path = arguments.area_output or os.path.join(
        arguments.output_root,
        "AreaToUIMapID_%s.lua" % arguments.client,
    )
    print("Wrote: %s" % convert(arguments.area_table_csv, output_path, arguments.ui_map, arguments.client, area_output_path))


if __name__ == "__main__":
    main()
