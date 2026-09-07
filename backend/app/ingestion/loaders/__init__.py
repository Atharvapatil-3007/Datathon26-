"""Concrete DataLoader implementations for each supported source format."""

from app.ingestion.loaders.csv_loader import CSVLoader
from app.ingestion.loaders.excel_loader import ExcelLoader
from app.ingestion.loaders.json_loader import JSONLoader
from app.ingestion.loaders.jsonl_loader import JSONLLoader
from app.ingestion.loaders.parquet_loader import ParquetLoader
from app.ingestion.loaders.sqlite_loader import SQLiteLoader
from app.ingestion.loaders.sql_loader import SQLLoader
from app.ingestion.loaders.zip_loader import ZIPLoader

__all__ = [
    "CSVLoader",
    "ExcelLoader",
    "JSONLoader",
    "JSONLLoader",
    "ParquetLoader",
    "SQLiteLoader",
    "SQLLoader",
    "ZIPLoader",
]
