"""Converte grandi file JSON in formato Parquet usando DuckDB.

Questo modulo fornisce un'utilità da riga di comando che legge un file JSON,
potenzialmente molto grande, e lo esporta in formato Parquet tramite DuckDB.
Lo script è pensato per dataset che possono non entrare comodamente in RAM
e configura DuckDB per usare una quantità limitata di memoria, appoggiandosi
a una directory temporanea su disco quando necessario.

Funzionalità principali:

- inferenza automatica del percorso di output Parquet;
- creazione della directory temporanea DuckDB accanto al file sorgente;
- visualizzazione di banner e messaggio di caricamento nel terminale;
- configurazione DuckDB ottimizzata per conversioni locali di grandi file;
- ignorare righe JSON malformate durante l'importazione;
- unione di schemi differenti con ``union_by_name=True``.

Autore:
    JumpFrost_ITA

Versione:
    1.0.0
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import duckdb


def clear_screen() -> None:
    """Pulisce lo schermo del terminale corrente.

    Usa il comando appropriato per la piattaforma in esecuzione in modo da
    ripulire il terminale prima di stampare il banner dell'applicazione.
    Su Windows invoca ``cls`` tramite ``cmd /c``; sui sistemi Unix-like
    invoca ``clear``.

    Il comando viene eseguito con ``check=False`` così il programma non si
    interrompe se il terminale non supporta l'operazione oppure se il comando
    non è disponibile.

    Returns:
        None
    """
    if sys.platform.startswith("win"):
        subprocess.run(["cmd", "/c", "cls"], check=False)
    else:
        subprocess.run(["clear"], check=False)


def print_banner() -> None:
    """Stampa il banner dell'applicazione.

    Mostra il banner ASCII usato dal tool da riga di comando, seguito da
    due righe centrate contenenti il nome dell'autore e la data del progetto.

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
    """Crea e restituisce il parser degli argomenti da riga di comando.

    Definisce l'interfaccia CLI del programma. Il percorso del file JSON
    sorgente è obbligatorio, mentre il percorso del file Parquet di output
    è opzionale. Se il file di destinazione non viene fornito, viene
    ricavato automaticamente a partire dal percorso sorgente.

    Returns:
        argparse.ArgumentParser: Istanza del parser configurato.
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
    """Determina il percorso finale del file Parquet di output.

    Se il parametro di destinazione non viene fornito, crea automaticamente
    il percorso di output nella stessa cartella del file sorgente, riusando
    lo stesso nome base e sostituendo l'estensione con ``.parquet``.
    Altrimenti converte il valore fornito in un oggetto ``Path``.

    Args:
        source_path (Path): Percorso del file JSON sorgente.
        destination (str | None): Percorso opzionale di destinazione passato
            dalla riga di comando.

    Returns:
        Path: Percorso finale del file Parquet di output.
    """
    if destination is None:
        return source_path.with_suffix(".parquet")
    return Path(destination)


def create_temp_directory(source_path: Path) -> Path:
    """Crea e restituisce la directory temporanea di lavoro per DuckDB.

    La directory temporanea viene creata accanto al file sorgente con il
    nome ``duckdb_tmp``. DuckDB può usarla per scrivere file temporanei su
    disco quando il carico di lavoro supera il working set gestibile in RAM.

    Args:
        source_path (Path): Percorso del file JSON sorgente.

    Returns:
        Path: Percorso della directory temporanea creata o riutilizzata.

    Raises:
        OSError: Se la directory non può essere creata a causa di permessi
            insufficienti o di uno stato non valido del filesystem.
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
    """Configura una connessione DuckDB per la conversione di file grandi.

    Applica le impostazioni runtime usate dal convertitore per bilanciare
    utilizzo della memoria, parallelismo, overhead dovuto alla preservazione
    dell'ordine di inserimento, uso della directory temporanea e visualizzazione
    della progress bar.

    Args:
        connection (duckdb.DuckDBPyConnection): Connessione DuckDB attiva.
        memory_limit (str): Limite massimo di memoria DuckDB, ad esempio
            ``16GB``.
        threads (int): Numero di thread di lavoro che DuckDB può usare.
        temp_directory (Path): Directory usata da DuckDB per i file temporanei.

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
    """Converte un file JSON in Parquet usando DuckDB.

    Esegue una query ``COPY`` che legge il file JSON sorgente tramite
    ``read_json_auto`` e scrive il dataset risultante in formato Parquet.
    Il lettore JSON viene configurato per ignorare le righe malformate e
    per unificare i campi per nome quando i record espongono variazioni
    di schema.

    Args:
        connection (duckdb.DuckDBPyConnection): Connessione DuckDB attiva.
        source_path (Path): Percorso del file JSON sorgente.
        destination_path (Path): Percorso del file Parquet di output.

    Returns:
        None

    Raises:
        duckdb.Error: Se DuckDB fallisce durante lettura, parsing,
            pianificazione o scrittura del file Parquet.
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
    """Valida il percorso del file sorgente prima della conversione.

    Verifica che il percorso fornito esista realmente e che punti a un file
    regolare. In caso contrario, interrompe l'esecuzione in anticipo con
    un'eccezione più chiara per l'utente.

    Args:
        source_path (Path): Percorso del file JSON sorgente.

    Returns:
        None

    Raises:
        FileNotFoundError: Se il percorso sorgente non esiste.
        ValueError: Se il percorso esiste ma non corrisponde a un file.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"File sorgente non trovato: {source_path}")

    if not source_path.is_file():
        raise ValueError(f"Il percorso sorgente non è un file valido: {source_path}")


def main() -> None:
    """Esegue il flusso principale della conversione JSON -> Parquet.

    Analizza gli argomenti da riga di comando, valida i percorsi, prepara la
    directory temporanea di DuckDB, pulisce il terminale, mostra il banner,
    configura DuckDB e avvia la conversione del file JSON in Parquet.

    Returns:
        None

    Raises:
        FileNotFoundError: Se il file sorgente non esiste.
        ValueError: Se il percorso sorgente non punta a un file regolare.
        OSError: Se la directory temporanea non può essere creata.
        duckdb.Error: Se DuckDB fallisce durante configurazione o conversione.
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
