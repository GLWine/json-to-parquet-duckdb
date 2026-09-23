import os
import time
from pathlib import Path

import duckdb


def convert_json_to_parquet(
    json_path: Path, parquet_path: Path, show_metrics: bool = True
) -> dict:
    """Converte un file JSON estratto in formato Parquet ottimizzato tramite DuckDB.

    Restituisce un dizionario contenente le metriche di conversione.
    """
    cpu_count = os.cpu_count() or 4
    start_time = time.time()

    con = duckdb.connect()
    con.execute(f"SET threads = {cpu_count};")
    con.execute("SET enable_progress_bar = true;")

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

    con.execute(
        query,
        {
            "input_json": str(json_path),
            "output_parquet": str(parquet_path),
        },
    )

    elapsed = time.time() - start_time
    json_size = json_path.stat().st_size
    parquet_size = parquet_path.stat().st_size if parquet_path.exists() else 0

    json_size_gb = json_size / (1024**3)
    parquet_size_mb = parquet_size / (1024**2)
    speed = (json_size / (1024**2)) / elapsed if elapsed > 0 else 0
    ratio = json_size / parquet_size if parquet_size > 0 else 0

    if show_metrics:
        print(
            f"   Conversione Parquet completata in {elapsed:.2f}s."
            f"\n   Output: {parquet_size_mb:.2f} MB | Compressione vs JSON: {ratio:.1f}x | Velocità lettura: {speed:.1f} MB/s"
        )

    return {
        "elapsed": elapsed,
        "json_size_gb": json_size_gb,
        "parquet_size_mb": parquet_size_mb,
        "speed_mb": speed,
        "ratio": ratio,
    }
