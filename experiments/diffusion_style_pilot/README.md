# Level 2 paper texture jobs

The [pilot plan](../../docs/plans/diffusion-style-pilot.md) contains the source shortlist, budget and evaluation protocol. These scripts run as standalone jobs under `heocr-remote`. Stage the inputs after eval clears the source and exact training labels. The lead approves any spend and handles queueing.

## GPU job input root

Copy `level2.sh`, `job-env.sh`, `level2.py`, `paper.py` and `contracts.py` to the policy-approved `in/` directory. Keep `inputs.json` in the parent directory so the manifest excludes itself. Use the GPU preflight invocation in the plan.

| Input | Contents |
| --- | --- |
| `style-crops.jsonl` | Each row has `source_id`, `page`, `png`, `sha256`, `crop_xywh` and `dpi`. Use relative paths and 64×64 grayscale crops from the one cleared edition. Keep the Commons file revision, work ID, rights and scan SHA-256 in the staged source record. |
| `train-labels.jsonl` | 1,000 records with `id` (full lowercase SHA-256 of the label's UTF-8 bytes) and `text` (logical NFC). The labels must pass the exact list overlap check. Keep the original line-index provenance in the job input. |
| `attestations.json` | Objects keyed by `style-crops` and `train-labels`. Each contains `status` (`CLEAR` or `CLEAN`, respectively), `sha256` of the corresponding JSONL and `record` containing an opaque reference to the eval decision. Preserve the decision and its link locally outside the upload root. |
| `render/` | Output of the governed `render-lines` command on the frozen label file with the plan's font, band and preset settings. Keep its complete manifest and rendered sidecars. |
| `tessdata/heb.traineddata` | The pinned float `tessdata_best` Hebrew model, shared by the first OCR reader and the matched OCR arms. |
| `reader/` | `charset_v2f.txt` and `server-svtrv2/{ctc,nrtr-encoder,nrtr-decstep}.onnx` from [the pinned Apache-2.0 model revision](https://huggingface.co/Rivok/paddleocr-hebrew/tree/c6bfad5d207024ef66927dd5d061308cb407a496). Retain upstream licence and notices. |
| `assets.json` | A mapping from each reader artifact's relative path to its SHA-256. The heocr-compute upload manifest separately hashes the full directory. |
| `gpu-requirements.lock` and `wheels/` | Hash-locked wheels for the GPU image's Linux x86-64 Python. Prepare and smoke-test the wheelhouse against the image before the paid run. The image supplies CUDA and PyTorch. |

Pin Diffusers `0.35.2` and build the reader wheel from [decoder commit `3baae91`](https://github.com/RivoksLab/paddleocr-hebrew/tree/3baae91ad6479ef0473f901b4ed96366ae6c1670). Resolve and hash the transitive wheels, including NumPy, Pillow, safetensors and CPU ONNX Runtime, using the intended image's Python version. Install the lock with `--require-hashes --no-index` on the pod. Tesseract and its training tools are checked at 5.5.3. If absent, the job installs Ubuntu build dependencies and compiles the pinned upstream revision. Confirm that packages, pinned image and the source repository are reachable in preflight.

For example, after `STAGE/in/train-labels.jsonl` is frozen, produce its render inputs from the renderer pinned in the plan.

```sh
hocrsyngen render-lines --input "$STAGE/in/train-labels.jsonl" --output "$STAGE/in/render" \
  --seed 20261121 --preset none --font frank-ruhl-libre --font david-libre-regular \
  --band-range 27 34
```

The GPU job re-arms the runner's self-termination timer before setup. After training, it returns scratch model weights, generated tiles, a data-quality report, `pairs.jsonl` and paired encodings. Review the runner's `SHA256SUMS` and confirm termination before using the results.

## Blinded label audit

Rebuild the exact pixel arrays for a deterministic sample of 50 accepted pairs. The script checks both image pixel hashes and the original mask. Give the independent reviewer only the `blind/` images. Compare their transcripts against `review-key.json` after review. Stop on any drift. A passing audit record binds the result to the hash of the full pair manifest.

```sh
python3 experiments/diffusion_style_pilot/audit_pairs.py "$STAGE/in" "$GPU_RESULT" "$AUDIT"
```

Use the `quality.json` rejection and confusable-pair counts to report data quality. The audit contains original label strings and stays with the private experiment record.

## Paired training job input root

Use a fresh policy-approved `in/` directory and stage `train-pair.sh`, `job-env.sh`, `train_pair.py` and `contracts.py`. Copy the verified `pairs.jsonl` and `paired/` results, the same `assets.json` and stock `tessdata/heb.traineddata`. Add `pair-audit.json` with `status: "PASS"`, `sha256` of `pairs.jsonl`, `examined_pairs: 50` and an opaque `record` for the audit decision. Use the CPU preflight invocation in the plan.

Both lists are derived from the same ordered record IDs and are checked against the recorded encodings. Three consecutive checkpoints per arm share one starter and iteration schedule. The job requires matching sample consumption without skips before marking `training.json` complete. Hand the checkpoints to eval for P-hist audit2 selection only after the job and teardown pass.
