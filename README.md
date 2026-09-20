# json-to-parquet-duckdb

CLI Python per convertire grandi file JSON in Parquet con DuckDB, pensata per dataset grossi che non stanno comodamente in RAM.

## Features

- Conversione JSON -> Parquet
- Supporto a file molto grandi
- Gestione errori con `ignore_errors = TRUE`
- Unione schema con `union_by_name = TRUE`
- Output di destinazione opzionale
- Configurazione DuckDB per memoria, thread e temp directory
- Banner CLI e progress bar

## Requisiti

- Python 3.10+
- DuckDB
- psutil

## Installazione

```bash
pip install duckdb psutil
```

## Uso

```bash
python json_to_parquet.py source.json
```

Salva automaticamente il file `.parquet` accanto al sorgente.

Oppure:

```bash
python json_to_parquet.py source.json output.parquet
```

## Come funziona

Il tool:

1. legge il file JSON sorgente;
2. crea automaticamente il file di output se non specificato;
3. crea una cartella temporanea DuckDB accanto al file sorgente;
4. configura DuckDB per lavorare con dataset grandi;
5. esporta in formato Parquet.

## Configurazione attuale

- `memory_limit = '16GB'`
- `threads = 4`
- `preserve_insertion_order = false`
- `temp_directory` nella cartella del file sorgente

## Note

- L'ordine originale delle righe può non essere preservato per migliorare l'uso della memoria.
- La progress bar dipende dal comportamento del client DuckDB/Python e può non essere sempre dettagliata in tempo reale.
- Il file sorgente deve essere accessibile localmente dal processo Python.

## Licenza

MIT
