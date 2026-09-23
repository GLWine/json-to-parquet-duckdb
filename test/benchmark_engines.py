import argparse
import sys
from pathlib import Path

# Aggiunge la radice del progetto a sys.path per trovare il modulo 'core'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_benchmark(gz_path: Path) -> None:
    """Esegue un benchmark comparativo tra i motori di decompressione disponibili

    sullo stesso file .json.gz.
    """
    from core.jsongz_to_json import decompress_jsongz

    gz_path = Path(gz_path).resolve()
    if not gz_path.exists():
        print(f"[ERRORE] File non trovato: {gz_path}")
        return

    engines = ["isal", "rapidgzip", "pgzip", "gzip"]
    results = []

    temp_dir = gz_path.parent / "benchmark_tmp"
    temp_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print(f" BENCHMARK MOTORI DECOMPRESSIONE GZIP: {gz_path.name}")
    print("=" * 70)

    for engine in engines:
        out_json = temp_dir / f"test_{engine}.json"
        print(f"\n[+] Test motore: {engine.upper()}...")

        try:
            metrics = decompress_jsongz(
                gz_path, out_json, engine=engine, show_metrics=False
            )
            results.append((engine, metrics))
            print(
                f"    Completato in {metrics['elapsed']:.2f}s | Velocità: {metrics['speed_mb']:.1f} MB/s"
            )
        except (RuntimeError, OSError, ValueError) as err:
            print(f"    [ERRORE] Motore {engine} fallito: {err}")
        finally:
            if out_json.exists():
                out_json.unlink()

    # Pulizia cartella temporanea del benchmark
    if temp_dir.exists():
        try:
            temp_dir.rmdir()
        except OSError:
            pass

    if not results:
        print("\n[ERRORE] Nessun motore ha completato il test.")
        return

    # Ordinamento dei risultati dal più veloce al più lento
    results.sort(key=lambda x: x[1]["elapsed"])
    best_time = results[0][1]["elapsed"]

    print("\n" + "=" * 70)
    print(" RISULTATI BENCHMARK (Ordinati dal più veloce)")
    print("=" * 70)
    print(
        f"{'MOTORE':<12} | {'TEMPO (s)':<10} | {'VELOCITÀ (MB/s)':<16} | {'GAP'}"
    )
    print("-" * 70)

    for engine, m in results:
        gap = (
            "1.00x (BEST)"
            if m["elapsed"] == best_time
            else f"{m['elapsed'] / best_time:.2f}x più lento"
        )
        print(
            f"{engine:<12} | {m['elapsed']:<10.2f} | {m['speed_mb']:<16.1f} | {gap}"
        )

    print("=" * 70 + "\n")


def main() -> None:
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
