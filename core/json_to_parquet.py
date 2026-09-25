"""Modulo per la conversione ad alte prestazioni da JSON a Parquet tramite DuckDB.

Utilizza il motore analitico DuckDB per eseguire letture strutturate ed
esportazioni in formato columnar Parquet con supporto multi-threading.
"""

import os
import time
from pathlib import Path

import duckdb


def _calculate_metrics(json_path: Path, parquet_path: Path, elapsed: float) -> dict:
    """Calcola le metriche di velocità, dimensione e compressione della conversione.

    Args:
        json_path: Percorso del file JSON analizzato.
        parquet_path: Percorso del file Parquet generato.
        elapsed: Tempo totale di esecuzione in secondi.

    Returns:
        Dizionario contenente le metriche elaborate.
    """
    json_size = json_path.stat().st_size
    parquet_size = parquet_path.stat().st_size if parquet_path.exists() else 0

    json_size_gb = json_size / (1024**3)
    parquet_size_mb = parquet_size / (1024**2)

    return {
        "elapsed": elapsed,
        "json_size_gb": json_size_gb,
        "parquet_size_mb": parquet_size_mb,
    }


def convert_json_to_parquet(
    json_path: Path,
    parquet_path: Path,
    show_metrics: bool = True,
    count_discarded: bool = False,
) -> dict:
    """Converte un file JSON estratto in formato Parquet ottimizzato tramite DuckDB.

    Args:
        json_path: Percorso assoluto o relativo del file JSON sorgente.
        parquet_path: Percorso assoluto o relativo del file Parquet di destinazione.
        show_metrics: Se True, stampa a schermo il riepilogo delle prestazioni.

    Returns:
        Dizionario contenente le metriche di conversione (tempo e dimensioni).

    Raises:
        FileNotFoundError: Se il file JSON sorgente non esiste nel filesystem.
    """
    json_path = Path(json_path).resolve()
    parquet_path = Path(parquet_path).resolve()

    if not json_path.exists():
        raise FileNotFoundError(f"File JSON non trovato: {json_path}")

    cpu_count = os.cpu_count() or 4
    start_time = time.time()

    # Configurazione ed esecuzione della conversione via DuckDB
    query = """
    COPY (
        SELECT *
        FROM read_json_auto(
            $input_json,
            sample_size = -1,
            union_by_name = true,
            ignore_errors = true
        )
    ) TO $output_parquet (
        FORMAT PARQUET
    );
    """

    with duckdb.connect() as con:
        con.execute(f"SET threads = {cpu_count};")
        con.execute("SET enable_progress_bar = true;")
        con.execute(
            query,
            {
                "input_json": str(json_path),
                "output_parquet": str(parquet_path),
            },
        )

    elapsed = time.time() - start_time
    metrics = _calculate_metrics(json_path, parquet_path, elapsed)

    if show_metrics:
        print(
            f"   Conversione Parquet completata in {metrics['elapsed']:.2f}s."
            f"\n   Output: {metrics['parquet_size_mb']:.2f} MB | "
        )

    return metrics
