# P-hist round v1: development disposition

The [registration](REGISTRATION.md) records the training and selection methods. R7 and its descendants inherit checkpoint-selection exposure to two sources later reserved in line_verify.

The R7-start arm's `heb_final` was selected on the audit2 development set. Its SHA-256 is `f8090760b5b02d09cf4ddb435e7a5e34089f6f17cde9cfb6c67fd06c6f17ec02`. The modern-print guards also used development material. Public results use [registered held-out sets of real documents](https://heocr.org/en/benchmarks.html).

## 1. Training (§4)

| | |
|---|---|
| Run | heocr-remote `20261118-175353-bdbd` |
| Pod | RunPod **`cpu3c` × 16 vCPUs** (pod `nhdaotqvsb5h7f`), $0.48/h; total **$0.81** |
| Deviation | §4 registered a 32-vCPU `cpu3c` pod. None was available, so the run used the 16-vCPU fallback. Both arms still ran side by side on the same pod, at OMP_THREAD_LIMIT=4 each. The recipe and iterations are unchanged. |
| Inputs | manifest `inputs.json` sha256 `250de59de77f6fd1353d68f2ddb88b5a4858ed33855a536429d67f1993b8733e`; the pod verified the starter, both lists and both labels sha256 before training. `train_phist.sh` sha256 `b2115990…`, `stage_remote.py` `edf92d70…`, `v1/manifest.json` `fa8f370d…` |
| Pulled back | 32 files, all sha256 OK |

## Selection and release

The selection used whole-page Tesseract reads and the registered punctuation folds. Differences between a reader's character set and the reference punctuation can affect a close selection. The development study did not authorize a model release.
