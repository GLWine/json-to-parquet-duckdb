import argparse
import shutil
from pathlib import Path

from core.jsongz_to_json import decompress_jsongz


def run_benchmark(gz_file: str) -> None:
    gz_path = Path(gz_file).resolve()
    if not gz_path.exists():
        print(f"[ERRORE] Il file '{gz_path}' non esiste.")
        return

    bench_dir = gz_path.parent / "benchmark_tmp"
    bench_dir.mkdir(exist_ok=True)
    tmp_json_path = bench_dir / "bench_output.json"

    engines = ["isal", "rapidgzip", "pgzip", "pigz", "gzip"]
    total_steps = len(engines)

    results = []
    print("=" * 70)
    print(f" START BENCHMARK DECOMPRESSIONE: {gz_path.name}")
    print(
        f" Dimensione file compresso: {gz_path.stat().st_size / (1024**3):.2f} GB"
    )
    print("=" * 70)

    for idx, engine in enumerate(engines, start=1):
        step_prefix = f"[{idx}/{total_steps}]"
        print(
            f"\n{step_prefix} Estrazione {gz_path.name} in corso [Motore: {engine.upper()}]..."
        )

        if tmp_json_path.exists():
            tmp_json_path.unlink()

        try:
            metrics = decompress_jsongz(
                gz_path, tmp_json_path, engine=engine, show_metrics=False
            )

            print(
                f"{step_prefix} Estrazione ({engine.lower()}) completata in {metrics['elapsed']:.2f}s."
                f"\n      Dati estratti: {metrics['final_size_gb']:.2f} GB | Ratio: {metrics['ratio']:.2f}x | Velocità reale: {metrics['speed_mb']:.1f} MB/s"
            )

            results.append(
                {
                    "engine": engine.upper(),
                    "time_sec": metrics["elapsed"],
                    "speed_mb": metrics["speed_mb"],
                    "ratio": metrics["ratio"],
                    "size_gb": metrics["final_size_gb"],
                    "status": "OK",
                }
            )

        except (RuntimeError, OSError, ValueError) as err:
            print(
                f"{step_prefix} [ERRORE] Il motore {engine} ha fallito: {err}"
            )
            results.append(
                {
                    "engine": engine.upper(),
                    "time_sec": 0,
                    "speed_mb": 0,
                    "ratio": 0,
                    "size_gb": 0,
                    "status": f"FAILED ({err})",
                }
            )

    if bench_dir.exists():
        shutil.rmtree(bench_dir)

    valid_results = [r for r in results if r["status"] == "OK"]
    valid_results.sort(key=lambda x: x["speed_mb"], reverse=True)

    # ---------------------------------------------------------
    # STAMPA TABELLA COMPARATIVA
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print(" TABELLA COMPARATIVA RISULTATI DECOMPRESSIONE")
    print("=" * 70)
    print(
        f"{'Pos.':<5} | {'Motore':<10} | {'Tempo (s)':<10} | {'Velocità (MB/s)':<16} | {'Ratio':<8} | {'Stato':<8}"
    )
    print("-" * 70)

    for pos, res in enumerate(valid_results, 1):
        print(
            f"{pos:<5} | {res['engine']:<10} | {res['time_sec']:<10.2f} | {res['speed_mb']:<16.1f} | {res['ratio']:<8.2f}x | {res['status']:<8}"
        )

    failed_results = [r for r in results if r["status"] != "OK"]
    for res in failed_results:
        print(
            f"{'-':<5} | {res['engine']:<10} | {'N/A':<10} | {'N/A':<16} | {'N/A':<8} | {res['status']}"
        )

    print("=" * 70)

    if valid_results:
        winner = valid_results[0]
        slowest = valid_results[-1]
        gain = (
            ((slowest["time_sec"] - winner["time_sec"]) / slowest["time_sec"])
            * 100
            if slowest["time_sec"] > 0
            else 0
        )
        print(
            f" VINCITORE: {winner['engine']} con {winner['speed_mb']:.1f} MB/s ({winner['time_sec']:.2f}s)"
        )
        print(
            f" Risparmio di tempo rispetto al più lento ({slowest['engine']}): -{gain:.1f}%"
        )
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark dei motori di decompressione per file .json.gz"
    )
    parser.add_argument(
        "gz_file", type=str, help="Percorso del file .json.gz da testare"
    )

    args = parser.parse_args()
    run_benchmark(args.gz_file)
