# json-to-parquet-duckdb

CLI Python per trasformare file JSON compatti `.json.gz` in Parquet tramite DuckDB, con una pipeline in due fasi:

1. decompressione del gzip in un file JSON intermedio;
2. import del JSON in DuckDB e esportazione diretta a Parquet.

Il progetto è pensato per dataset grandi e per lavorare senza dover caricare tutto in RAM.

## Funzionalità

- Supporto diretto a file `.json.gz`
- Decompressione con più motori: `isal`, `rapidgzip`, `pgzip`, `pigz`, `gzip`
- Esecuzione opzionale solo della fase di decompressione
- Possibilità di mantenere il file JSON intermedio
- Output automatico in una cartella dedicata al nome del file sorgente
- Import JSON con `read_json_auto`, `union_by_name = true`, `ignore_errors = true`
- Metriche di tempo, velocità e rapporto di compressione
- Progress bar durante la decompressione e il lavoro di DuckDB

## Requisiti

- Python 3.10+
- DuckDB
- `tqdm`
- uno o più motori di decompressione disponibili:
  - `isal`
  - `rapidgzip`
  - `pgzip`
  - `pigz` (o eseguibile nel PATH / `lib/pigz.exe` su Windows)
  - `gzip` (stdlib di Python)

## Installazione

Dal root del progetto:

```bash
pip install -r requirements.txt
pip install duckdb
```

Se vuoi usare i motori extra, installa anche i pacchetti corrispondenti:

```bash
pip install isal rapidgzip pgzip
```

## Uso

Esempio base:

```bash
python main.py .\galaxy_7days.json.gz
```

Questo crea una cartella chiamata `galaxy_7days/` accanto al file sorgente e genera:

- `galaxy_7days/galaxy_7days.json` (file intermedio, eliminato di default)
- `galaxy_7days/galaxy_7days.parquet` (output finale)

### Selezione del motore di decompressione

```bash
python main.py .\galaxy_7days.json.gz --engine rapidgzip
```

Motori disponibili:

- `isal`
- `rapidgzip`
- `pgzip`
- `pigz`
- `gzip`

### Solo decompressione

```bash
python main.py .\galaxy_7days.json.gz --decompress-only
```

In questo modo viene creato solo il file JSON intermedio senza convertire in Parquet.

### Mantenere il JSON intermedio

```bash
python main.py .\galaxy_7days.json.gz --keep-json
```

Il JSON non viene rimosso dopo la conversione.

## Pipeline attuale

Il comando principale avvia questa workflow:

1. verifica che il file `.json.gz` esista;
2. crea una cartella di output con il nome del file senza estensione;
3. decompone il gzip in un file `.json` intermedio;
4. legge il JSON con DuckDB usando `read_json_auto`;
5. esporta il risultato in Parquet usando `COPY ... TO ... FORMAT PARQUET`;
6. rimuove il JSON intermedio se `--keep-json` non è stato usato.

## Output e struttura

Un esempio pratico:

```text
project/
├── main.py
├── core/
│   ├── jsongz_to_json.py
│   └── json_to_parquet.py
├── galaxy_7days/
│   ├── galaxy_7days.json
│   └── galaxy_7days.parquet
└── ...
```

## Configurazione impostata

Il progetto configura DuckDB in modo da lavorare bene su dataset grandi:

- `threads = numero di CPU disponibili`
- `enable_progress_bar = true`
- `sample_size = -1`
- `union_by_name = true`
- `ignore_errors = true`

## Note

- Il file sorgente deve essere leggibile localmente dal processo Python.
- La barra di avanzamento dipende dal comportamento di DuckDB e del runtime Python, quindi può non essere perfettamente granularizzata in tutti i casi.
- L'ordine delle righe del JSON originale non è garantito come ordine di output del Parquet.
- Il JSON intermedio viene rimosso per impostazione predefinita per alleggerire lo spazio su disco.

## Licenza

MIT
