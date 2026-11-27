# Demo dashboard (simulated passes)

`index.html` shows one pass each of corn, vineyard and potato: the 3D surface (or, for the vineyard, each
photographed row face), a top-down map, the places to look, and for each one the photos that show it with
the flagged area boxed. Everything in `data/` comes from simulated passes rendered in Blender and says so.

Serve the folder and open it (`python -m http.server` in this folder). `#corn`, `#vineyard` and `#potato`
pick the crop. The Photoreal button is disabled until the GPU splats from handoff 002 exist.

Rebuild `data/` from a processed pass with `pipelines/fieldpass/export_viewer.py` (see its docstring).
