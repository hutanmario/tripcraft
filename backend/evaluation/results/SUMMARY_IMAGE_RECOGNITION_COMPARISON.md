# Image Recognition Evaluation Comparison

Generated at: `2026-06-12T11:30:38.456842+00:00`

## Best Run

- Best by NDCG@5: `prompt_calibrated`
- P@3 delta vs `current_pipeline`: `0.4893`
- R@5 delta vs `current_pipeline`: `0.6099`
- NDCG@5 delta vs `current_pipeline`: `0.5945`
- Zero-hit@5 delta vs `current_pipeline`: `-0.6809`

## Runs

| Run | P@3 | R@5 | F1@5 | Hit-rate@5 | MRR@5 | MAP@5 | NDCG@5 | Zero-hit@5 | Report |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| prompt_calibrated | 0.6099 | 0.7305 | 0.5479 | 1.0 | 0.9113 | 0.6223 | 0.7272 | 0.0 | `SUMMARY_IMAGE_RECOGNITION_EVAL_prompt_calibrated.md` |
| prompt_uncalibrated | 0.4965 | 0.6312 | 0.4734 | 1.0 | 0.8862 | 0.5255 | 0.644 | 0.0 | `SUMMARY_IMAGE_RECOGNITION_EVAL_prompt_uncalibrated.md` |
| current_pipeline | 0.1206 | 0.1206 | 0.0904 | 0.3191 | 0.234 | 0.0922 | 0.1327 | 0.6809 | `SUMMARY_IMAGE_RECOGNITION_EVAL_current_pipeline.md` |

## Interpretation

- `P@3` masoara cat de curate sunt primele 3 taguri afisate.
- `R@5` masoara cat din ground truth este recuperat in top 5.
- `NDCG@5` recompenseaza hiturile gasite mai sus in ranking.
- `Zero-hit@5` este rata imaginilor unde niciun tag asteptat nu apare in top 5; mai mic este mai bine.
