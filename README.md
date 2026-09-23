# json.gz-to-parquet-duckdb

Pipeline Python per convertire file JSON compatti `.json.gz` in Parquet usando DuckDB.

La trasformazione avviene in due passaggi:

1. decompressione del gzip in un file JSON intermedio;
2. lettura del JSON con DuckDB ed esportazione diretta in Parquet.

Il progetto è pensato per dataset di grandi dimensioni e per evitare di caricare tutto in memoria.

## Funzionalità attuali

- supporto diretto a file `.json.gz`;
- decompressione con più motori disponibili: `isal`, `rapidgzip`, `pgzip`, `gzip`;
- esecuzione facoltativa solo della fase di decompressione;
- persistenza opzionale del file JSON intermedio tramite `--keep-json`;
- output automatico in una cartella dedicata al nome del file sorgente;
- import JSON con `read_json_auto`, `sample_size = -1`, `union_by_name = true`, `ignore_errors = true`;
- metriche di tempo, velocità e rapporto di compressione;
- progress bar durante decompressione e conversione.

## Requisiti

- Python 3.10+
- DuckDB
- `tqdm`
- uno o più motori di decompressione disponibili:
  - `isal`
  - `rapidgzip`
  - `pgzip`
  - `gzip` (standard library di Python)

Il file `requirements.txt` include i pacchetti principali del progetto:

```bash
isal>=1.1.0
rapidgzip>=0.14.0
pgzip>=0.3.0
tqdm>=4.66.0
```

## Installazione

Dal root del progetto:

```bash
pip install -r requirements.txt
pip install duckdb
```

Se vuoi usare i motori extra installali esplicitamente:

```bash
pip install isal rapidgzip pgzip
```

## Uso

Esempio base:

```bash
python main.py .\galaxy_7days.json.gz
```

Il comando crea una cartella con lo stesso nome del file senza estensione, ad esempio `galaxy_7days/`, e produce:

- `galaxy_7days/galaxy_7days.json` (file intermedio, eliminato di default);
- `galaxy_7days/galaxy_7days.parquet` (output finale).

### Selezione del motore di decompressione

```bash
python main.py .\galaxy_7days.json.gz --engine rapidgzip
```

Motori supportati:

- `isal`
- `rapidgzip`
- `pgzip`
- `gzip`

### Solo decompressione

```bash
python main.py .\galaxy_7days.json.gz --decompress-only
```

In questo caso viene generato solo il file JSON intermedio e la conversione in Parquet non viene eseguita.

### Mantenere il file JSON intermedio

```bash
python main.py .\galaxy_7days.json.gz --keep-json
```

Con questa opzione il file `.json` non viene rimosso dopo aver generato il Parquet.

## Pipeline attuale

La CLI esegue oggi questa sequenza:

1. verifica che il file `.json.gz` esista;
2. crea la directory di output nel percorso del file sorgente usando il nome base senza estensione;
3. decompone il file gzip in un JSON intermedio;
4. legge il JSON con DuckDB tramite `read_json_auto`;
5. esporta i dati in Parquet tramite `COPY ... TO ... FORMAT PARQUET`;
6. elimina il JSON intermedio se `--keep-json` non è specificato.

## Configurazione DuckDB

La conversione imposta in modo implicito:

- `threads = numero di CPU disponibili`;
- `enable_progress_bar = true`;
- `sample_size = -1`;
- `union_by_name = true`;
- `ignore_errors = true`.

## Struttura del progetto

```text
project/
├── main.py
├── README.md
├── requirements.txt
├── core/
│   ├── __init__.py
│   ├── jsongz_to_json.py
│   └── json_to_parquet.py
├── test/
│   └── benchmark_engines.py
├── galaxy_7days/
│   ├── galaxy_7days.json
│   └── galaxy_7days.parquet
└── ...
```

## Benchmark di confronto tra motori

Il progetto include anche uno script per confrontare i tempi dei diversi motori di decompressione:

```bash
python .\test\benchmark_engines.py .\galaxy_7days.json.gz
```

Lo script esegue test sequenziali per `isal`, `rapidgzip`, `pgzip` e `gzip`, ordina i risultati dal più veloce al più lento e stampa una tabella comparativa.

## Note

- il file sorgente deve essere leggibile localmente dal processo Python;
- la progress bar dipende dal terminale e dal runtime di esecuzione, quindi può non essere perfettamente granularizzata in tutti i casi;
- l'ordine delle righe del JSON originale non è garantito come ordine di output del Parquet;
- il file JSON intermedio viene rimosso per impostazione predefinita per risparmiare spazio su disco.

## Licenza

MIT
