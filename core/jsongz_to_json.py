"""Modulo per la decompressione ad alte prestazioni di archivi .json.gz.

Supporta molteplici motori di decompressione multithread e ad alta velocità
(isal, rapidgzip, pgzip, gzip) con tracciamento dell'avanzamento tramite tqdm.
"""

import gzip
import os
import shutil
import time
from pathlib import Path
from typing import IO, Any

from tqdm import tqdm

VALID_ENGINES = ["isal", "rapidgzip", "pgzip", "gzip"]
BUFFER_SIZE = 8 * 1024 * 1024  # 8 MB


def _get_decompressor_stream(
    engine_type: str, open_file_handle: IO[bytes], cpu_count: int
) -> Any:
    """Istanzia e restituisce il file-stream decompresso in base al motore richiesto.

    Args:
        engine_type: Il nome del motore da utilizzare ('isal', 'rapidgzip', 'pgzip', 'gzip').
        open_file_handle: Stream binario aperto in sola lettura per il file .gz.
        cpu_count: Numero di thread/core CPU da assegnare per il parallelismo.

    Returns:
        Un oggetto stream decorato pronto per la lettura binaria decompresso.
    """
    if engine_type == "isal":
        from isal import igzip

        return igzip.IGzipFile(fileobj=open_file_handle, mode="rb")

    if engine_type == "gzip":
        return gzip.GzipFile(fileobj=open_file_handle, mode="rb")

    if engine_type == "pgzip":
        import pgzip

        return pgzip.PgzipFile(
            fileobj=open_file_handle,
            mode="rb",
            thread=cpu_count,
            blocksize=BUFFER_SIZE,
        )

    # rapidgzip
    import rapidgzip

    return rapidgzip.open(open_file_handle, parallelization=cpu_count)


def _decompress_with_progress(
    f_in: Any,
    f_out: IO[bytes],
    open_file_handle: IO[bytes],
    gz_size: int,
    engine_type: str,
    half_width: int,
) -> None:
    """Esegue il ciclo di lettura/scrittura a blocchi aggiornando la progress bar tqdm.

    Args:
        f_in: Stream di decompressione in lettura.
        f_out: Stream binario di destinazione in scrittura.
        open_file_handle: Stream del file sorgente .gz per tracciare i byte letti.
        gz_size: Dimensione totale in byte del file .gz sorgente.
        engine_type: Nome del motore in esecuzione (utilizzato nella descrizione).
        half_width: Larghezza in caratteri per la formattazione della progress bar.
    """
    with (
        f_in,
        tqdm(
            total=gz_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=f"Lettura .gz ({engine_type})",
            ncols=half_width,
            leave=True,
        ) as pbar,
    ):
        while True:
            chunk = f_in.read(BUFFER_SIZE)
            if not chunk:
                break
            f_out.write(chunk)
            pbar.update(open_file_handle.tell() - pbar.n)


def decompress_jsongz(
    gz_path: Path,
    json_path: Path,
    engine: str = "isal",
    show_metrics: bool = True,
) -> dict:
    """Decomprime un file .json.gz in un file .json usando il motore specificato.

    Args:
        gz_path: Percorso assoluto o relativo del file .json.gz sorgente.
        json_path: Percorso assoluto o relativo del file .json estratto di destinazione.
        engine: Motore di decompressione da utilizzare ('isal', 'rapidgzip', 'pgzip', 'gzip').
        show_metrics: Se True, stampa a schermo il riepilogo delle prestazioni.

    Returns:
        Dizionario contenente le metriche di esecuzione (tempo, dimensioni, velocità, ratio).

    Raises:
        ValueError: Se il motore specificato non rientra tra quelli supportati.
        FileNotFoundError: Se il file .json.gz sorgente non esiste nel filesystem.
    """
    engine_type = engine.lower()
    if engine_type not in VALID_ENGINES:
        raise ValueError(
            f"Motore '{engine}' non valido. Scegli tra: {', '.join(VALID_ENGINES)}."
        )

    gz_path = Path(gz_path).resolve()
    json_path = Path(json_path).resolve()

    if not gz_path.exists():
        raise FileNotFoundError(f"File non trovato: {gz_path}")

    terminal_width = shutil.get_terminal_size().columns
    half_width = max(20, terminal_width // 2)
    gz_size = gz_path.stat().st_size
    cpu_count = os.cpu_count() or 4
    start_time = time.time()

    with (
        open(gz_path, "rb") as open_file_handle,
        open(json_path, "wb") as f_out,
    ):
        f_in = _get_decompressor_stream(
            engine_type, open_file_handle, cpu_count
        )
        _decompress_with_progress(
            f_in, f_out, open_file_handle, gz_size, engine_type, half_width
        )

    # Calcolo metriche di esecuzione
    elapsed = time.time() - start_time
    json_size = json_path.stat().st_size if json_path.exists() else 0
    final_size_gb = json_size / (1024**3)
    speed = (json_size / (1024**2)) / elapsed if elapsed > 0 else 0
    ratio = json_size / gz_size if gz_size > 0 else 0

    if show_metrics:
        print(
            f"      Estrazione ({engine_type}) completata in {elapsed:.2f}s."
            f"\n      Dati estratti: {final_size_gb:.2f} GB | Ratio: {ratio:.2f}x | Velocità reale: {speed:.1f} MB/s"
        )

    return {
        "elapsed": elapsed,
        "json_size": json_size,
        "final_size_gb": final_size_gb,
        "speed_mb": speed,
        "ratio": ratio,
    }
