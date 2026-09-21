"""Converte JSON/GZ Spansh in Parquet tramite DuckDB con inferenza configurabile."""

from __future__ import annotations

import argparse
import gzip
import logging
import tempfile
import time
from pathlib import Path

import duckdb

LOGGER = logging.getLogger("spansh_converter")
COPY_BUFFER_SIZE = 8 * 1024 * 1024


def configure_logging(verbose: bool) -> None:
    """Configura il logging della CLI."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def format_size(value: int | float) -> str:
    """Formatta byte in unita leggibili."""
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{value} B"


def sql_literal(value: str) -> str:
    """Restituisce un literal SQL DuckDB quotato."""
    return "'" + value.replace("'", "''") + "'"


def decompress_gzip(source: Path, destination: Path, interval: float) -> int:
    """Decomprime il file gzip con avanzamento su una sola riga."""
    LOGGER.info("Decompressione avviata: %s", source)
    started = time.monotonic()
    last_update = started
    total = 0

    with (
        source.open("rb") as compressed_file,
        destination.open("wb") as json_file,
        gzip.GzipFile(fileobj=compressed_file, mode="rb") as gzip_stream,
    ):
        while chunk := gzip_stream.read(COPY_BUFFER_SIZE):
            json_file.write(chunk)
            total += len(chunk)
            now = time.monotonic()
            if now - last_update >= interval:
                elapsed = max(now - started, 0.001)
                print(
                    f"\r[decompressione] {format_size(total)} | "
                    f"{format_size(total / elapsed)}/s",
                    end="",
                    flush=True,
                )
                last_update = now

    elapsed = max(time.monotonic() - started, 0.001)
    print(
        f"\r[decompressione] completata: {format_size(total)} | "
        f"{format_size(total / elapsed)}/s" + " " * 10,
        flush=True,
    )
    LOGGER.info("Decompressione completata: %s", format_size(total))
    return total


def configure_duckdb(
    connection: duckdb.DuckDBPyConnection,
    memory_limit: str,
    threads: int,
    temp_directory: Path,
) -> None:
    """Configura le risorse DuckDB."""
    connection.execute(f"SET memory_limit = {sql_literal(memory_limit)}")
    connection.execute(f"SET threads = {threads}")
    connection.execute("SET preserve_insertion_order = false")
    connection.execute(f"SET temp_directory = {sql_literal(str(temp_directory))}")
    connection.execute("SET enable_progress_bar = true")
    connection.execute("SET enable_progress_bar_print = true")


def build_json_reader(
    source: Path,
    json_format: str,
    union_by_name: bool,
    ignore_errors: bool,
    sample_size: int,
    maximum_depth: int,
) -> str:
    """Costruisce read_json_auto con opzioni di inferenza esplicite."""
    options = [
        f"format = {sql_literal(json_format)}",
        f"sample_size = {sample_size}",
        f"maximum_depth = {maximum_depth}",
    ]
    if union_by_name:
        options.append("union_by_name = true")
    if ignore_errors:
        options.append("ignore_errors = true")
    return f"read_json_auto({sql_literal(str(source))}, {', '.join(options)})"


def convert_json_to_parquet(
    connection: duckdb.DuckDBPyConnection,
    source: Path,
    destination: Path,
    json_format: str,
    union_by_name: bool,
    ignore_errors: bool,
    sample_size: int,
    maximum_depth: int,
) -> None:
    """Converte il JSON in Parquet con COPY DuckDB."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    reader = build_json_reader(
        source,
        json_format,
        union_by_name,
        ignore_errors,
        sample_size,
        maximum_depth,
    )
    query = f"""
        COPY (SELECT * FROM {reader})
        TO {sql_literal(str(destination))}
        (FORMAT PARQUET);
    """
    LOGGER.info("Conversione DuckDB avviata")
    connection.execute(query)
    LOGGER.info("Conversione DuckDB completata")


def build_parser() -> argparse.ArgumentParser:
    """Costruisce il parser CLI."""
    parser = argparse.ArgumentParser(
        description="Converte dump Spansh JSON/GZ in Parquet con DuckDB."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--format",
        dest="json_format",
        choices=("auto", "array", "newline_delimited", "unstructured"),
        default="array",
    )
    parser.add_argument("--memory-limit", default="6GB")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--temp-directory", type=Path)
    parser.add_argument("--union-by-name", action="store_true")
    parser.add_argument("--ignore-errors", action="store_true")
    parser.add_argument("--sample-size", type=int, default=100000)
    parser.add_argument("--maximum-depth", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--progress-interval", type=float, default=1.0)
    return parser


def main() -> None:
    """Esegue decompressione, conversione e pulizia."""
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)

    if not args.source.is_file():
        parser.error(f"File sorgente non trovato: {args.source}")
    if args.threads <= 0 or args.sample_size <= 0 or args.maximum_depth <= 0:
        parser.error("threads, sample-size e maximum-depth devono essere positivi.")
    if args.progress_interval <= 0:
        parser.error("progress-interval deve essere positivo.")

    destination = args.output or args.source.with_suffix(".parquet")
    if destination.exists() and not args.overwrite:
        parser.error(f"Output già esistente; usa --overwrite: {destination}")

    with tempfile.TemporaryDirectory(
        prefix="spansh_duckdb_", dir=args.temp_directory
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        source_for_duckdb = args.source
        if args.source.suffix.lower() == ".gz":
            source_for_duckdb = temporary_root / args.source.stem
            decompress_gzip(args.source, source_for_duckdb, args.progress_interval)

        connection = duckdb.connect()
        try:
            configure_duckdb(
                connection,
                args.memory_limit,
                args.threads,
                temporary_root / "duckdb_tmp",
            )
            convert_json_to_parquet(
                connection,
                source_for_duckdb,
                destination,
                args.json_format,
                args.union_by_name,
                args.ignore_errors,
                args.sample_size,
                args.maximum_depth,
            )
        finally:
            connection.close()

    print(f"Completato: {destination}")


if __name__ == "__main__":
    main()
