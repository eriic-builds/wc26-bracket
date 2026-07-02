# input/ — drop your source files here

This folder is where you upload the **two source files** used to build the dashboard.
They are read **once** to generate the dashboard; after that the dashboard doesn't depend
on them.

## What to upload

1. **`instructions.md`** — the *instructions kit* (the build spec).
   Tells how the dashboard should look and behave: layout, sections, and the **scoring rules**
   for grading your picks against actual results.

2. **`bracket-picks.xlsx`** — your *picks data*.
   The teams, seeds, match ids, your predicted winners, and (if present) dates/kickoff times.

## After you upload

Once both files are here, the dashboard is generated into **`../docs/index.html`** and your
results tracker is seeded into **`../docs/results.json`**.

> Keep the exact filenames above (`instructions.md`, `bracket-picks.xlsx`) so the build can
> find them. If you use different names, just say so and they'll be wired up.
