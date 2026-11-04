"""Importacion CSV con staging (RF-CSV-01..13, RNF-CSV-01..11).

Endpoint /imports: plantilla por entidad, upload multipart con validacion
estricta de columnas, staging en Postgres, review de filas y confirmacion
transaccional. Adapters por entidad en ``adapters/``.
"""
