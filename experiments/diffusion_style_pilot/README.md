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
| `assets.json` | Copy `reader-assets.json` into `in/assets.json`. It pins the exact reader artifacts by relative path and SHA-256. The heocr-compute upload manifest separately hashes the full directory. |
| `gpu-requirements.lock` and `wheels/` | Hash-locked wheels for the GPU image's Linux x86-64 Python 3.12. Copy the committed `gpu-requirements.lock` and assemble its matching wheels. Verify the offline wheelhouse before the paid run. The image supplies CUDA and PyTorch 2.8.0. The resolved AMD64 image digest at preparation was `sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851`. Check it again before launch. |

The lock pins Diffusers `0.35.2`, NumPy, Pillow, safetensors and the CPU ONNX Runtime. Build the reader wheel from [decoder commit `3baae91`](https://github.com/RivoksLab/paddleocr-hebrew/tree/3baae91ad6479ef0473f901b4ed96366ae6c1670) with setuptools `84.2.1` and `SOURCE_DATE_EPOCH=1795176000`, and verify the wheel against the lock. The remaining locked wheels are from PyPI. Install the lock with `--require-hashes --no-index` on the pod. Tesseract and its training tools are checked at 5.5.3. If absent, the job installs Ubuntu build dependencies and compiles the pinned upstream revision. Confirm that packages, pinned image and the source repository are reachable in preflight.

For example, after `STAGE/in/train-labels.jsonl` is frozen, produce its render inputs from the renderer pinned in the plan.

```sh
hocrsyngen render-lines --input "$STAGE/in/train-labels.jsonl" --output "$STAGE/in/render" \
  --seed 20261121 --preset none --font frank-ruhl-libre --font david-libre-regular \
  --band-range 27 34
```

The GPU job re-arms the runner's self-termination timer before setup. After training, it returns scratch model weights, generated tiles, a data-quality report and `accepted.jsonl`. The generic runner filters `.lstmf` from its result pull, so the CPU training encodings are staged locally after the audit. Review the runner's `SHA256SUMS` and confirm termination before using the results.

## Blinded label audit

Rebuild the exact pixel arrays for a deterministic sample of 50 accepted pairs. The script checks both image pixel hashes and the original mask. Give the independent reviewer only the `blind/` images. Compare their transcripts against `review-key.json` after review. Stop on any drift. A passing audit record binds the result to the hash of `accepted.jsonl`. Save it with `status: "PASS"`, `accepted_sha256` from the review key, `examined_pairs: 50` and an opaque `record` for the review decision.

```sh
python3 experiments/diffusion_style_pilot/audit_pairs.py "$STAGE/in" "$GPU_RESULT" "$AUDIT"
```

Use the `quality.json` rejection and confusable-pair counts to report data quality. The audit contains original label strings and stays with the private experiment record.

## Paired training job input root

Use local Tesseract 5.5.3, the verified GPU result and the passing audit to build the CPU job's `in/` directory under a policy-approved parent. The stager reconstructs each pair, verifies both pixel hashes and writes the training files, pair manifest and hash-bound audit together. An encoding failure rejects the staging operation.

```sh
python3 experiments/diffusion_style_pilot/stage_pairs.py "$STAGE/in" "$GPU_RESULT" "$AUDIT_PASS" "$PAIR/in"
```

Stage `train-pair.sh`, `job-env.sh`, `train_pair.py` and `contracts.py` in that directory. Use the CPU preflight invocation in the plan.

Both lists are derived from the same ordered record IDs and are checked against the recorded encodings. Three consecutive checkpoints per arm share one starter and iteration schedule. The job requires matching sample consumption without skips before marking `training.json` complete. Hand the checkpoints to eval for P-hist audit2 selection only after the job and teardown pass.
