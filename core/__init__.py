"""Modulo core per la decompressione e conversione di file .json.gz a .parquet.

Espone le funzioni principali della pipeline di trasformazione dati.
"""

from .json_to_parquet import convert_json_to_parquet
from .jsongz_to_json import decompress_jsongz

__all__ = ["convert_json_to_parquet", "decompress_jsongz"]
