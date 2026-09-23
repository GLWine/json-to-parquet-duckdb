import gzip
import os
import shutil
import subprocess
import time
from pathlib import Path

from tqdm import tqdm


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
    valid_engines = ["isal", "rapidgzip", "pgzip", "pigz", "gzip"]
    if engine_type not in valid_engines:
        raise ValueError(
            f"Motore '{engine}' non valido. Scegli tra: {', '.join(valid_engines)}."
        )

    terminal_width = shutil.get_terminal_size().columns
    half_width = max(20, terminal_width // 2)
    gz_size = gz_path.stat().st_size
    start_time = time.time()

    # ---------------------------------------------------------
    # CASO SPECIALIZZATO: pigz (Stream via stdin)
    # ---------------------------------------------------------
    if engine_type == "pigz":
        # .parent (cartella core) -> .parent (radice del progetto) -> lib / pigz.exe
        project_root = Path(__file__).resolve().parent.parent
        pigz_exe = project_root / "lib" / "pigz.exe"

        if not pigz_exe.exists():
            system_pigz = shutil.which("pigz")
            if system_pigz:
                pigz_cmd = system_pigz
            else:
                raise FileNotFoundError(
                    f"Eseguibile pigz non trovato in '{pigz_exe}' e non presente nel PATH di sistema."
                )
        else:
            pigz_cmd = str(pigz_exe)

        cmd = [pigz_cmd, "-d", "-c"]
        buffer_size = 8 * 1024 * 1024

        with (
            open(gz_path, "rb") as f_in,
            open(json_path, "wb") as f_out,
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
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=f_out,
                stderr=subprocess.PIPE,
            )

            while True:
                chunk = f_in.read(buffer_size)
                if not chunk:
                    break
                if process.stdin:
                    process.stdin.write(chunk)
                pbar.update(len(chunk))

            if process.stdin:
                process.stdin.close()
            process.wait()

            if process.returncode != 0:
                stderr_msg = (
                    process.stderr.read().decode("utf-8", errors="replace")
                    if process.stderr
                    else ""
                )
                raise RuntimeError(
                    f"Errore durante l'esecuzione di pigz: {stderr_msg}"
                )

    # ---------------------------------------------------------
    # CASI LIBRERIE PYTHON: isal, pgzip, rapidgzip, gzip
    # ---------------------------------------------------------
    else:
        cpu_count = os.cpu_count() or 4
        buffer_size = 8 * 1024 * 1024

        with (
            open(gz_path, "rb") as open_file_handle,
            open(json_path, "wb") as f_out,
        ):
            if engine_type == "isal":
                from isal import igzip

                f_in = igzip.IGzipFile(fileobj=open_file_handle, mode="rb")
            elif engine_type == "gzip":
                f_in = gzip.GzipFile(fileobj=open_file_handle, mode="rb")
            elif engine_type == "pgzip":
                import pgzip

                f_in = pgzip.PgzipFile(
                    fileobj=open_file_handle,
                    mode="rb",
                    thread=cpu_count,
                    blocksize=buffer_size,
                )
            else:  # rapidgzip
                import rapidgzip

                f_in = rapidgzip.open(
                    open_file_handle, parallelization=cpu_count
                )

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
                    chunk = f_in.read(buffer_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    pbar.update(open_file_handle.tell() - pbar.n)

    # ---------------------------------------------------------
    # CALCOLO METRICHE E RITORNO DATI
    # ---------------------------------------------------------
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
