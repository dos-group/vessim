# Vessim Viewer

Browser-based experiment viewer for Vessim simulation results. Reads `metadata.yaml` and `timeseries.csv` from a results directory. No running simulation required.

## Usage

The easiest way is via the CLI:

```bash
vessim view results/my_experiment
```

This serves the pre-built viewer and opens it in your browser. Alternatively, open the viewer directly (`npm run dev`) and use the file picker to load a results directory.

## Development

```bash
cd viewer
npm install
npm run dev       # Start dev server with hot reload
npm run build     # Production build → dist/
```

After building, copy the output into the Python package:

```bash
rm -rf ../vessim/_viewer_dist && cp -r dist ../vessim/_viewer_dist
```

## Stack

React, TypeScript, Vite, Tailwind CSS, Recharts. YAML/CSV parsing happens client-side via js-yaml and PapaParse.
