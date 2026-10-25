# Legacy platform notes

- Teradata 17.20. All jobs run through BTEQ in Teradata (session) mode, not ANSI mode.
- DBS Control: RoundHalfwayMagUp = FALSE (the default).
- Character data in the source tables comes from fixed-width extracts and hand-maintained reference tables, so
  values can carry trailing spaces and inconsistent letter case.
- Each job writes one output table, named in its `-- OUTPUT:` header, keyed by its `-- KEY:` header.
- Target platform: DuckDB. The migrated jobs must reproduce the legacy outputs exactly, row for row.
