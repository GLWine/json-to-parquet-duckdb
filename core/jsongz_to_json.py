import gzip
import os
import shutil
import time
from pathlib import Path
from typing import BinaryIO

from tqdm import tqdm

VALID_ENGINES = ["isal", "rapidgzip", "pgzip", "gzip"]
BUFFER_SIZE = 8 * 1024 * 1024  # 8 MB


def _get_decompressor_stream(
    engine_type: str, open_file_handle: BinaryIO, cpu_count: int
) -> BinaryIO:
    """Istanzia e restituisce il file-stream decompresso in base al motore richiesto."""
    if engine_type == "isal":
        from isal import igzip

        return igzip.IGzipFile(fileobj=open_file_handle, mode="rb")  # type: ignore[return-value]

    if engine_type == "gzip":
        return gzip.GzipFile(fileobj=open_file_handle, mode="rb")  # type: ignore[return-value]

    if engine_type == "pgzip":
        import pgzip

        return pgzip.PgzipFile(
            fileobj=open_file_handle,
            mode="rb",
            thread=cpu_count,
            blocksize=BUFFER_SIZE,
        )  # type: ignore[return-value]

    # rapidgzip
    import rapidgzip

    return rapidgzip.open(open_file_handle, parallelization=cpu_count)


def _decompress_with_progress(
    f_in: BinaryIO,
    f_out: BinaryIO,
    open_file_handle: BinaryIO,
    gz_size: int,
    engine_type: str,
    half_width: int,
) -> None:
    """Esegue il ciclo di lettura/scrittura a blocchi aggiornando la progress bar tqdm."""
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

    Restituisce un dizionario contenente le metriche di esecuzione.
    """
    engine_type = engine.lower()
    if engine_type not in VALID_ENGINES:
        raise ValueError(
            f"Motore '{engine}' non valido. Scegli tra: {', '.join(VALID_ENGINES)}."
        )

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
    json_size = json_path.stat().st_size
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
