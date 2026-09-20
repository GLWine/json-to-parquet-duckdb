"""Convert large JSON files to Parquet format using DuckDB.

This module provides a command-line utility that reads a potentially large
JSON file and writes a Parquet file using DuckDB. The tool is designed for
datasets that may not fit comfortably in memory, and it configures DuckDB
to use a bounded amount of RAM plus a temporary spill directory on disk.

The script can:

- infer the output Parquet path automatically;
- create a temporary DuckDB working directory next to the source file;
- show a banner and a loading message in the terminal;
- configure DuckDB for large local conversions;
- ignore malformed JSON rows during import;
- merge schema variations with ``union_by_name=True``.

Author:
    JumpFrost_ITA

Version:
    1.0.0
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import duckdb


def clear_screen() -> None:
    """Clear the current terminal screen.

    Use the platform-appropriate shell command to clear the visible terminal
    before printing the application banner. On Windows the function calls
    ``cls`` through ``cmd /c``; on Unix-like systems it calls ``clear``.

    The command is executed with ``check=False`` so the program does not stop
    if the screen cannot be cleared, for example when running in a terminal
    that does not support the requested command.

    Returns:
        None
    """
    if sys.platform.startswith("win"):
        subprocess.run(["cmd", "/c", "cls"], check=False)
    else:
        subprocess.run(["clear"], check=False)


def print_banner() -> None:
    """Print the application banner.

    Render the ASCII-art banner used by the command-line tool, followed by
    centered metadata lines for the author name and project date.

    Returns:
        None
    """
    raw_banner = r"""
+----------------------------------------------------------------------------------------------------------------------------------+
|                                                                                                                                  |
|                                                                                                                                  |
|          ██╗███████╗ ██████╗ ███╗   ██╗    ████████╗ ██████╗     ██████╗  █████╗ ██████╗  ██████╗ ██╗   ██╗███████╗████████╗     |
|          ██║██╔════╝██╔═══██╗████╗  ██║    ╚══██╔══╝██╔═══██╗    ██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██║   ██║██╔════╝╚══██╔══╝     |
|          ██║███████╗██║   ██║██╔██╗ ██║       ██║   ██║   ██║    ██████╔╝███████║██████╔╝██║   ██║██║   ██║█████╗     ██║        |
|      ██   ██║╚════██║██║   ██║██║╚██╗██║       ██║   ██║   ██║    ██╔═══╝ ██╔══██║██╔══██╗██║▄▄ ██║██║   ██║██╔══╝     ██║        |
|      ╚█████╔╝███████║╚██████╔╝██║ ╚████║       ██║   ╚██████╔╝    ██║     ██║  ██║██║  ██║╚██████╔╝╚██████╔╝███████╗   ██║        |
|       ╚════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝       ╚═╝    ╚═════╝     ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚══▀▀═╝  ╚═════╝ ╚══════╝   ╚═╝        |
|                                                                                                                                  |
|                                                                                                                                  |
+----------------------------------------------------------------------------------------------------------------------------------+
"""
    inner_width = 130
    name_line = "| " + "By: JumpFrost_ITA".center(inner_width) + " |"
    date_line = "| " + "2024-06-05".center(inner_width) + " |"
    border = "+" + "-" * (inner_width + 2) + "+"

    print(raw_banner)
    print(name_line)
    print(date_line)
    print(border)


def build_parser() -> argparse.ArgumentParser:
    """Create and return the command-line argument parser.

    Define the CLI interface for the program. The source JSON path is required,
    while the destination Parquet path is optional. If the destination is not
    provided, it is derived automatically from the source path.

    Returns:
        argparse.ArgumentParser: The configured argument parser instance.
    """
    parser = argparse.ArgumentParser(
        description="Converti un JSON grande in Parquet usando DuckDB."
    )
    parser.add_argument("source", help="Percorso del file JSON sorgente.")
    parser.add_argument(
        "destination",
        nargs="?",
        help="Percorso del file Parquet di destinazione (opzionale).",
    )
    return parser


def resolve_destination_path(
    source_path: Path,
    destination: str | None,
) -> Path:
    """Resolve the final Parquet output path.

    If the destination argument is not provided, create the output path in the
    same directory as the source file and reuse the same base filename with the
    ``.parquet`` extension. Otherwise, convert the provided destination string
    into a ``Path`` object.

    Args:
        source_path (Path): Path to the source JSON file.
        destination (str | None): Optional destination path passed from the CLI.

    Returns:
        Path: The resolved Parquet destination path.
    """
    if destination is None:
        return source_path.with_suffix(".parquet")
    return Path(destination)


def create_temp_directory(source_path: Path) -> Path:
    """Create and return the DuckDB temporary working directory.

    The temporary directory is created next to the source file, using the name
    ``duckdb_tmp``. DuckDB can use this location for temporary spill files when
    the workload exceeds the in-memory working set.

    Args:
        source_path (Path): Path to the source JSON file.

    Returns:
        Path: The path of the created or reused temporary directory.

    Raises:
        OSError: If the directory cannot be created due to permission issues
            or an invalid filesystem state.
    """
    temp_dir = source_path.parent / "duckdb_tmp"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


def configure_duckdb(
    connection: duckdb.DuckDBPyConnection,
    memory_limit: str,
    threads: int,
    temp_directory: Path,
) -> None:
    """Configure a DuckDB connection for large-file conversion.

    Apply the runtime settings used by the converter to balance memory usage,
    parallelism, insertion-order overhead, temporary spill behavior, and
    progress bar display.

    Args:
        connection (duckdb.DuckDBPyConnection): Active DuckDB connection.
        memory_limit (str): Maximum DuckDB memory budget, for example ``16GB``.
        threads (int): Number of DuckDB worker threads to use.
        temp_directory (Path): Directory used by DuckDB for temporary files.

    Returns:
        None
    """
    connection.execute(f"SET memory_limit = '{memory_limit}'")
    connection.execute(f"SET threads = {threads}")
    connection.execute("SET preserve_insertion_order = false")
    connection.execute(f"SET temp_directory = '{temp_directory}'")
    connection.execute("SET enable_progress_bar = true")
    connection.execute("SET enable_progress_bar_print = true")


def convert_json_to_parquet(
    connection: duckdb.DuckDBPyConnection,
    source_path: Path,
    destination_path: Path,
) -> None:
    """Convert a JSON file to Parquet using DuckDB.

    Execute a DuckDB ``COPY`` statement that reads the source JSON file with
    ``read_json_auto`` and writes the resulting dataset to Parquet. The JSON
    reader is configured to ignore malformed rows and to merge fields by name
    when records expose schema differences.

    Args:
        connection (duckdb.DuckDBPyConnection): Active DuckDB connection.
        source_path (Path): Path to the source JSON file.
        destination_path (Path): Path to the output Parquet file.

    Returns:
        None

    Raises:
        duckdb.Error: If DuckDB fails during reading, parsing, planning, or
            writing the Parquet output.
    """
    connection.execute(
        f"""
        COPY (
            SELECT *
            FROM read_json_auto(
                '{source_path}',
                ignore_errors = TRUE,
                union_by_name = TRUE
            )
        )
        TO '{destination_path}'
        (FORMAT PARQUET);
        """
    )


def validate_source_path(source_path: Path) -> None:
    """Validate the source JSON path before starting the conversion.

    Ensure that the provided source path exists and points to a regular file.
    Fail early with a user-friendly exception if the path is invalid.

    Args:
        source_path (Path): Path to the source JSON file.

    Returns:
        None

    Raises:
        FileNotFoundError: If the source path does not exist.
        ValueError: If the source path exists but is not a regular file.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"File sorgente non trovato: {source_path}")

    if not source_path.is_file():
        raise ValueError(f"Il percorso sorgente non è un file valido: {source_path}")


def main() -> None:
    """Run the command-line JSON-to-Parquet conversion workflow.

    Parse CLI arguments, validate paths, prepare the DuckDB temporary
    directory, clear the terminal, display the banner, configure DuckDB, and
    launch the JSON-to-Parquet conversion.

    Returns:
        None

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If the source path is not a regular file.
        OSError: If the temporary directory cannot be created.
        duckdb.Error: If DuckDB fails during configuration or conversion.
    """
    parser = build_parser()
    args = parser.parse_args()

    source_path = Path(args.source)
    validate_source_path(source_path)

    destination_path = resolve_destination_path(source_path, args.destination)

    memory_limit = "16GB"
    num_threads = 4
    temp_dir = create_temp_directory(source_path)

    clear_screen()
    print_banner()
    print("\ncaricamento...\n")

    connection = duckdb.connect()
    try:
        configure_duckdb(
            connection=connection,
            memory_limit=memory_limit,
            threads=num_threads,
            temp_directory=temp_dir,
        )
        convert_json_to_parquet(
            connection=connection,
            source_path=source_path,
            destination_path=destination_path,
        )
    finally:
        connection.close()

    print(f"\nCompletato: {destination_path}\n")


if __name__ == "__main__":
    main()
