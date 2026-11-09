#!/usr/bin/env python3
"""Batch-download selected Wago DB2 CSV exports for supported WoW clients."""

import argparse
import csv
import io
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CLIENT_BUILDS = {
    "Mainline": "12.1.5.70783",
    "ClassicEra": "1.15.9.70576",
    "ClassicTBC": "2.5.6.70577",
    "ClassicForever": "1.60.1.70862",
    "ClassicProgression": "5.5.4.70631",
}

TABLE_COLUMNS = {
    "AreaTable": ("ID", "AreaName_lang"),
    "JournalInstance": ("ID", "Name_lang"),
    "LFGDungeons": ("ID", "Name_lang"),
    "Map": ("ID", "MapName_lang"),
    "UiMap": ("ID", "Name_lang"),
    "WMOAreaTable": ("AreaName_lang", "ID"),
    "TaxiNodes": ("Name_lang", "ID"),
}

LOCALES = (
    "enUS",
    "deDE",
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

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
BASE_URL = "https://wago.tools/db2"
USER_AGENT = "LibBabble-SubZone-3.0 CSV maintenance downloader"


def build_jobs(output_root, clients, locales, tables):
    for client in clients:
        build = CLIENT_BUILDS[client]
        for locale in locales:
            for table in tables:
                query = urlencode({"build": build, "locale": locale})
                url = "%s/%s/csv?%s" % (BASE_URL, table, query)
                filename = "%s.%s_%s.csv" % (table, build, locale)
                output_path = Path(output_root) / build / filename
                yield client, build, locale, table, url, output_path


def validate_csv(payload, table, source_url):
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV is not UTF-8: %s" % source_url) from error

    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if not header:
        raise ValueError("CSV response is empty: %s" % source_url)

    required_columns = set(TABLE_COLUMNS[table])
    actual_columns = {column.strip() for column in header}
    missing_columns = required_columns - actual_columns
    if missing_columns:
        raise ValueError(
            "CSV response for %s is missing columns: %s"
            % (table, ", ".join(sorted(missing_columns)))
        )


def retry_delay(error, attempt, minimum_delay):
    retry_after = error.headers.get("Retry-After") if isinstance(error, HTTPError) else None
    if retry_after:
        try:
            return max(minimum_delay, float(retry_after))
        except ValueError:
            pass
    return minimum_delay * (2 ** attempt)


def download_csv(url, output_path, table, timeout, retries, delay):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None

    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
            validate_csv(payload, table, url)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = output_path.with_suffix(output_path.suffix + ".part")
            try:
                temporary_path.write_bytes(payload)
                os.replace(temporary_path, output_path)
            finally:
                if temporary_path.exists():
                    temporary_path.unlink()
            return len(payload)
        except HTTPError as error:
            last_error = error
            if error.code not in RETRYABLE_STATUS_CODES or attempt >= retries:
                raise
        except (URLError, TimeoutError) as error:
            last_error = error
            if attempt >= retries:
                raise
        except ValueError:
            raise

        time.sleep(retry_delay(last_error, attempt, delay))

    raise last_error


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clients",
        nargs="+",
        choices=sorted(CLIENT_BUILDS),
        default=list(CLIENT_BUILDS),
        help="clients to download (default: all five)",
    )
    parser.add_argument(
        "--locales",
        nargs="+",
        choices=LOCALES,
        default=list(LOCALES),
        help="locales to download (default: all supported locales)",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=sorted(TABLE_COLUMNS),
        default=list(TABLE_COLUMNS),
        help="tables to download (default: all supported tables)",
    )
    parser.add_argument("--output-root", default=".data", help="download root directory")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=45.0, help="request timeout in seconds")
    parser.add_argument("--retries", type=int, default=3, help="retries for transient failures")
    parser.add_argument("--overwrite", action="store_true", help="replace existing CSV files")
    parser.add_argument("--dry-run", action="store_true", help="show the request plan without downloading")
    parser.add_argument("--limit", type=int, help="process at most this many planned downloads")
    arguments = parser.parse_args()

    if arguments.delay < 0:
        parser.error("--delay must be non-negative")
    if arguments.timeout <= 0:
        parser.error("--timeout must be positive")
    if arguments.retries < 0:
        parser.error("--retries must be non-negative")
    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be positive")
    return arguments


def main():
    arguments = parse_arguments()
    jobs = list(build_jobs(
        arguments.output_root,
        arguments.clients,
        arguments.locales,
        arguments.tables,
    ))
    if arguments.limit is not None:
        jobs = jobs[:arguments.limit]

    downloaded = 0
    skipped = 0
    failed = []
    for client, build, locale, table, url, output_path in jobs:
        if output_path.exists() and not arguments.overwrite:
            skipped += 1
            print("Skip existing: %s" % output_path)
            continue

        if arguments.dry_run:
            print("Would download [%s/%s/%s]: %s" % (client, build, locale, url))
            continue

        if downloaded:
            time.sleep(arguments.delay)
        print("Downloading [%s/%s/%s]: %s" % (client, build, locale, table))
        try:
            byte_count = download_csv(
                url,
                output_path,
                table,
                arguments.timeout,
                arguments.retries,
                arguments.delay,
            )
            downloaded += 1
            print("  Saved %s (%d bytes)" % (output_path, byte_count))
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            failed.append((url, str(error)))
            print("  Failed: %s" % error)

    if arguments.dry_run:
        print("Dry run: %d request(s) planned." % len(jobs))
        return 0

    print("Finished: %d downloaded, %d skipped, %d failed." % (downloaded, skipped, len(failed)))
    if failed:
        print("Failed URLs:")
        for url, error in failed:
            print("  %s: %s" % (url, error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())