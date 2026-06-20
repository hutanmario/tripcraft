# Image Runtime Benchmark

Generated at: `2026-06-12T11:09:34.108517+00:00`
Dataset: `C:\Users\mario\Desktop\licenta final\tripcraft\backend\evaluation\image_recognition_dataset.json`
Limit: `full`

## Environment

- Python: `3.14.4`
- Platform: `Windows-11-10.0.26200-SP0`
- Torch threads: `10`

## Results

| Pipeline | Images | Wall time | sec/img | Peak RAM MB | P@3 | R@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| current_pipeline | 47 | 249.93 | 5.3563 | 2123.68 | 0.1277 | 0.1277 | 0.139 | 0.6596 |
| prompt_top2_mean | 47 | 95.318 | 2.0622 | 2139.2 | 0.4823 | 0.6028 | 0.6195 | 0.0638 |

## Notes

- Wall time include pornirea procesului, importurile Python si incarcarea modelelor.
- Peak RAM este `PeakWorkingSetSize` al procesului copil pe Windows.
- `pipeline_reported_time_sec` din JSON exclude o parte din overhead-ul de startup, dar include inferenta pipeline-ului.

## Files

- JSON: `image_runtime_benchmark.json`
- CSV: `image_runtime_benchmark.csv`
