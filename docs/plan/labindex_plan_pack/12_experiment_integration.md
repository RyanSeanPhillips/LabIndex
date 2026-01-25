# 12 — Experiment/Project Integration

## Why
A high-quality index becomes a reusable substrate for experiment dashboards and animal-level project management apps.

## Core API (suggested)
- `build_experiment_bundle(file_id | animal_id, constraints) -> ExperimentBundle`
- `find_notes(file_id)`
- `find_surgeries(animal_id)`
- `find_histology(animal_id)`
- `export_bundle(bundle_id, format=json/zip)` (metadata only)

## Normalization path (optional)
Start with `entities_json`, later add:
- animals(animal_id, aliases, sex/strain, …)
- sessions(session_id, animal_id, date, rig, …)
- procedures(procedure_id, animal_id, virus/coords, …)

## Curation overlays
Store curated truth in a separate local DB/schema as overlays; never reorganize the drive.
