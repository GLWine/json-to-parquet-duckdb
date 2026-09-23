import argparse
from pathlib import Path
from typing import NamedTuple

from core import convert_json_to_parquet, decompress_jsongz


class PipelinePaths(NamedTuple):
    gz_path: Path
    output_dir: Path
    json_out_path: Path
    parquet_out_path: Path


def build_parser() -> argparse.ArgumentParser:
    """Configura e restituisce il parser degli argomenti da linea di comando."""

    def create_formatter(prog: str) -> argparse.HelpFormatter:
        return argparse.HelpFormatter(prog, max_help_position=40)

    parser = argparse.ArgumentParser(
        description="Pipeline di conversione ad alte prestazioni da .json.gz a .parquet tramite DuckDB",
        formatter_class=create_formatter,
    )
    parser.add_argument(
        "gz_file", type=str, help="Percorso del file .json.gz da processare"
    )
    parser.add_argument(
        "-e",
        "--engine",
        type=str,
        default="isal",
        choices=["isal", "rapidgzip", "pgzip", "gzip"],
        metavar="ENGINE",
        help="Motore di decompressione: isal, rapidgzip, pgzip, gzip (default: isal)",
    )
    parser.add_argument(
        "-d",
        "--decompress-only",
        action="store_true",
        help="Esegue solo la fase di decompressione senza proseguire con Parquet",
    )
    parser.add_argument(
        "-k",
        "--keep-json",
        action="store_true",
        help="Mantiene il file .json intermedio dopo la creazione del .parquet",
    )
    return parser


def prepare_pipeline_paths(gz_file_arg: str) -> PipelinePaths:
    """Risolve i percorsi di input/output e crea la directory di destinazione."""
    gz_path = Path(gz_file_arg).resolve()
    if not gz_path.exists():
        raise FileNotFoundError(f"Il file '{gz_path}' non esiste.")

    base_name = gz_path.name.split(".")[0]
    output_dir = gz_path.parent / base_name
    output_dir.mkdir(exist_ok=True)

    json_out_path = output_dir / f"{base_name}.json"
    parquet_out_path = output_dir / f"{base_name}.parquet"

    return PipelinePaths(
        gz_path=gz_path,
        output_dir=output_dir,
        json_out_path=json_out_path,
        parquet_out_path=parquet_out_path,
    )


def run_decompression_step(
    paths: PipelinePaths, engine: str, step_prefix: str
) -> dict | None:
    """Esegue lo step di decompressione da .json.gz a .json."""

    print(
        f"\n{step_prefix} Estrazione {paths.gz_path.name} in corso [Motore: {engine.upper()}]..."
    )
    try:
        metrics = decompress_jsongz(
            paths.gz_path,
            paths.json_out_path,
            engine=engine,
            show_metrics=False,
        )
        print(
            f"{step_prefix} Estrazione ({engine.lower()}) completata in {metrics['elapsed']:.2f}s."
            f"\n      Dati estratti: {metrics['final_size_gb']:.2f} GB | Ratio: {metrics['ratio']:.2f}x | Velocità reale: {metrics['speed_mb']:.1f} MB/s"
        )
        return metrics
    except (RuntimeError, OSError, ValueError) as err:
        print(f"{step_prefix} [ERRORE FATALE] Decompressione fallita: {err}")
        return None


def run_parquet_step(paths: PipelinePaths, step_prefix: str) -> dict | None:
    """Esegue lo step di conversione da .json a .parquet tramite DuckDB."""

    print(f"\n{step_prefix} Conversione JSON -> Parquet con DuckDB in corso...")
    try:
        metrics = convert_json_to_parquet(
            paths.json_out_path, paths.parquet_out_path, show_metrics=False
        )
        print(
            f"{step_prefix} Conversione Parquet completata con successo in {metrics['elapsed']:.2f}s."
            f"\n      Output: {metrics['parquet_size_mb']:.2f} MB | Compressione vs JSON: {metrics['ratio']:.1f}x | Velocità lettura: {metrics['speed_mb']:.1f} MB/s"
        )
        return metrics
    except (RuntimeError, OSError, ValueError) as err:
        print(
            f"{step_prefix} [ERRORE FATALE] Conversione Parquet fallita: {err}"
        )
        return None


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        paths = prepare_pipeline_paths(args.gz_file)
    except FileNotFoundError as err:
        print(f"[ERRORE] {err}")
        return

    total_steps = 1 if args.decompress_only else 2

    print("=" * 70)
    print(f" START PIPELINE: {paths.gz_path.name}")
    print(f" Cartella di output: {paths.output_dir}")
    print("=" * 70)

    # FASE 1: Decompressione
    gz_metrics = run_decompression_step(
        paths, engine=args.engine, step_prefix=f"[1/{total_steps}]"
    )
    if not gz_metrics:
        return

    if args.decompress_only:
        print("\n" + "=" * 70)
        print(" PIPELINE COMPLETATA (Solo Decompressione)")
        print(f" File JSON generato: {paths.json_out_path}")
        print("=" * 70 + "\n")
        return

    # FASE 2: Conversione Parquet
    pq_metrics = run_parquet_step(paths, step_prefix=f"[2/{total_steps}]")
    if not pq_metrics:
        return

    # Cleanup del file JSON intermedio
    if not args.keep_json and paths.json_out_path.exists():
        paths.json_out_path.unlink()

    # RIEPILOGO FINALE
    total_time = gz_metrics["elapsed"] + pq_metrics["elapsed"]
    print("\n" + "=" * 70)
    print(" PIPELINE COMPLETATA CON SUCCESSO")
    print(f" Tempo totale impiegato: {total_time:.2f}s")
    print(f" Output Parquet: {paths.parquet_out_path}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
