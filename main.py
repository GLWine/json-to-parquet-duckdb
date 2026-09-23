import argparse
from pathlib import Path

from core import convert_json_to_parquet, decompress_jsongz


def main() -> None:
    # Funzione Helper per estendere lo spazio dei flag nell'help (PEP 8 compliant)
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
        choices=["isal", "rapidgzip", "pgzip", "pigz", "gzip"],
        metavar="ENGINE",
        help="Motore di decompressione: isal, rapidgzip, pgzip, pigz, gzip (default: isal)",
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

    args = parser.parse_args()

    gz_path = Path(args.gz_file).resolve()
    if not gz_path.exists():
        print(f"[ERRORE] Il file '{gz_path}' non esiste.")
        return

    # Definizione del numero totale di passaggi della pipeline
    total_steps = 1 if args.decompress_only else 2

    # Generazione dei percorsi di output
    base_name = gz_path.name.split(".")[0]
    output_dir = gz_path.parent / base_name
    output_dir.mkdir(exist_ok=True)

    json_out_path = output_dir / f"{base_name}.json"
    parquet_out_path = output_dir / f"{base_name}.parquet"

    print("=" * 70)
    print(f" START PIPELINE: {gz_path.name}")
    print(f" Cartella di output: {output_dir}")
    print("=" * 70)

    # ---------------------------------------------------------
    # FASE 1: Decompressione JSON.GZ -> JSON
    # ---------------------------------------------------------
    step_prefix = f"[1/{total_steps}]"
    print(
        f"\n{step_prefix} Estrazione {gz_path.name} in corso [Motore: {args.engine.upper()}]..."
    )

    try:
        gz_metrics = decompress_jsongz(
            gz_path, json_out_path, engine=args.engine, show_metrics=False
        )

        print(
            f"{step_prefix} Estrazione ({args.engine.lower()}) completata in {gz_metrics['elapsed']:.2f}s."
            f"\n      Dati estratti: {gz_metrics['final_size_gb']:.2f} GB | Ratio: {gz_metrics['ratio']:.2f}x | Velocità reale: {gz_metrics['speed_mb']:.1f} MB/s"
        )

    except (RuntimeError, OSError, ValueError) as err:
        print(f"{step_prefix} [ERRORE FATALE] Decompressione fallita: {err}")
        return

    if args.decompress_only:
        print("\n" + "=" * 70)
        print(" PIPELINE COMPLETATA (Solo Decompressione)")
        print(f" File JSON generato: {json_out_path}")
        print("=" * 70 + "\n")
        return

    # ---------------------------------------------------------
    # FASE 2: Conversione JSON -> Parquet con DuckDB
    # ---------------------------------------------------------
    step_prefix = f"[2/{total_steps}]"
    print(f"\n{step_prefix} Conversione JSON -> Parquet con DuckDB in corso...")

    try:
        pq_metrics = convert_json_to_parquet(
            json_out_path, parquet_out_path, show_metrics=False
        )

        print(
            f"{step_prefix} Conversione Parquet completata con successo in {pq_metrics['elapsed']:.2f}s."
            f"\n      Dimensione Parquet: {pq_metrics['parquet_size_mb']:.2f} MB | Compressione vs JSON: {pq_metrics['ratio']:.1f}x | Velocità: {pq_metrics['speed_mb']:.1f} MB/s"
        )

    except (RuntimeError, OSError, ValueError) as err:
        print(
            f"{step_prefix} [ERRORE FATALE] Conversione Parquet fallita: {err}"
        )
        return

    # Rimuove il file JSON intermedio se non esplicitamente richiesto di mantenerlo
    if not args.keep_json and json_out_path.exists():
        json_out_path.unlink()

    # ---------------------------------------------------------
    # RIEPILOGO FINALE
    # ---------------------------------------------------------
    total_time = gz_metrics["elapsed"] + pq_metrics["elapsed"]
    print("\n" + "=" * 70)
    print(" PIPELINE COMPLETATA CON SUCCESSO")
    print(f" Tempo totale impiegato: {total_time:.2f}s")
    print(f" Output Parquet: {parquet_out_path}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
