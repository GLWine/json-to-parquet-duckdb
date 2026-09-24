"""Script per il benchmark comparativo dei motori di decompressione per file .json.gz.

Esegue test sequenziali sulle prestazioni dei motori 'isal', 'rapidgzip', 'pgzip' e 'gzip'
sullo stesso file di input, ripulendo i file temporanei e stampando una tabella comparativa.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

# Aggiunge la radice del progetto a sys.path per rendere accessibile il pacchetto 'core'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import decompress_jsongz

ENGINES = ["isal", "rapidgzip", "pgzip", "gzip"]


def _execute_single_engine_test(
    engine: str, gz_path: Path, temp_dir: Path
) -> tuple[str, dict[str, Any]] | None:
    """Esegue il test di decompressione per un singolo motore.

    Args:
        engine: Nome del motore da testare.
        gz_path: Percorso del file .json.gz sorgente.
        temp_dir: Directory temporanea per l'output JSON.

    Returns:
        Una tupla (nome_motore, dizionario_metriche) oppure None se il test fallisce.
    """
    out_json = temp_dir / f"test_{engine}.json"
    print(f"\n[+] Test motore: {engine.upper()}...")

    try:
        metrics = decompress_jsongz(
            gz_path, out_json, engine=engine, show_metrics=False
        )
        print(
            f"    Completato in {metrics['elapsed']:.2f}s | Velocità: {metrics['speed_mb']:.1f} MB/s"
        )
        return engine, metrics
    except (RuntimeError, OSError, ValueError) as err:
        print(f"    [ERRORE] Motore {engine} fallito: {err}")
        return None
    finally:
        if out_json.exists():
            out_json.unlink()


def _cleanup_temp_dir(temp_dir: Path) -> None:
    """Tenta la rimozione della directory temporanea del benchmark.

    Args:
        temp_dir: Directory da eliminare.
    """
    if temp_dir.exists():
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def _print_benchmark_summary(results: list[tuple[str, dict[str, Any]]]) -> None:
    """Ordina e stampa a schermo la tabella riassuntiva dei risultati del benchmark.

    Args:
        results: Lista di tuple contenenti il nome del motore e le sue metriche.
    """
    results.sort(key=lambda x: x[1]["elapsed"])
    best_time = results[0][1]["elapsed"]

    print("\n" + "=" * 70)
    print(" RISULTATI BENCHMARK (Ordinati dal più veloce)")
    print("=" * 70)
    print(f"{'MOTORE':<12} | {'TEMPO (s)':<10} | {'VELOCITÀ (MB/s)':<16} | {'GAP'}")
    print("-" * 70)

    for engine, m in results:
        gap = (
            "1.00x (BEST)"
            if m["elapsed"] == best_time
            else f"{m['elapsed'] / best_time:.2f}x più lento"
        )
        print(f"{engine:<12} | {m['elapsed']:<10.2f} | {m['speed_mb']:<16.1f} | {gap}")

    print("=" * 70 + "\n")


def run_benchmark(gz_path: Path) -> None:
    """Orchestra ed esecuta il benchmark comparativo tra i motori supportati.

    Args:
        gz_path: Percorso assoluto o relativo del file .json.gz da testare.
    """
    gz_path = Path(gz_path).resolve()
    if not gz_path.exists():
        print(f"[ERRORE] File non trovato: {gz_path}")
        return

    temp_dir = gz_path.parent / "benchmark_tmp"
    temp_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print(f" BENCHMARK MOTORI DECOMPRESSIONE GZIP: {gz_path.name}")
    print("=" * 70)

    results: list[tuple[str, dict[str, Any]]] = []

    for engine in ENGINES:
        res = _execute_single_engine_test(engine, gz_path, temp_dir)
        if res:
            results.append(res)

    _cleanup_temp_dir(temp_dir)

    if not results:
        print("\n[ERRORE] Nessun motore ha completato il test con successo.")
        return

    _print_benchmark_summary(results)


def main() -> None:
    """Punto di ingresso dello script CLI di benchmark."""
    parser = argparse.ArgumentParser(
        description="Benchmark delle prestazioni dei motori di decompressione per file .json.gz"
    )
    parser.add_argument(
        "gz_file", type=str, help="Percorso del file .json.gz su cui testare i motori"
    )

    args = parser.parse_args()
    run_benchmark(Path(args.gz_file))


if __name__ == "__main__":
    main()
