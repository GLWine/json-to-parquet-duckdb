
import argparse
import subprocess
import sys
from pathlib import Path

import duckdb


def clear_screen():
    if sys.platform.startswith("win"):
        subprocess.run(["cmd", "/c", "cls"], check=False)
    else:
        subprocess.run(["clear"], check=False)


def print_banner():
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


def main():
    parser = argparse.ArgumentParser(
        description="Converti un JSON grande in Parquet usando DuckDB"
    )
    parser.add_argument("source", help="Percorso del file JSON sorgente")
    parser.add_argument(
        "destination",
        nargs="?",
        help="Percorso del file Parquet di destinazione (opzionale)",
    )
    args = parser.parse_args()

    source_path = Path(args.source)

    if args.destination is None:
        destination_path = source_path.with_suffix(".parquet")
    else:
        destination_path = Path(args.destination)

    memoria_massima = "16GB"
    num_threads = 4

    temp_dir = source_path.parent / "duckdb_tmp"
    temp_dir.mkdir(exist_ok=True)

    clear_screen()
    print_banner()
    print("\ncaricamento...\n")

    con = duckdb.connect()

    con.execute(f"SET memory_limit = '{memoria_massima}'")
    con.execute(f"SET threads = {num_threads}")
    con.execute("SET preserve_insertion_order = false")
    con.execute(f"SET temp_directory = '{temp_dir}'")
    con.execute("SET enable_progress_bar = true")
    con.execute("SET enable_progress_bar_print = true")

    con.execute(f"""
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
    """)

    con.close()

    print(f"\nCompletato: {destination_path}\n")


if __name__ == "__main__":
    main()
