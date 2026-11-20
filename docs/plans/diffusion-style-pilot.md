# Diffusion style pilot: stage 1 proposal

Stage 1 specifies the approved Level 2 design. Source clearance and approval to spend are pending (2026-11-20). The question is whether a gently styled synthetic training arm improves recognition of real historical print over the same untransformed arm. A prior fine-tuned model showed no gain over stock on PS-v1 real photos; improvement here is unmeasured on a held-out set. Stage 1 is a feasibility pilot, not a promise of improvement or release.

## Candidate levels

| Level | Method and connection | Advantages | Risks and gate |
| --- | --- | --- | --- |
| 1. Glyph | Few-shot style transfer in the FontDiffuser or DG-Font class from individually identified glyphs in a cleared PD printer; curate a complete Hebrew glyph set and use normal rendering or the S16 glyph-bank/composer contract. | Character assignment and line labels are constructed from the rendering text; style can follow a printer. | A generated glyph can look like another character despite its assigned code point; expert inspection and confusion-pair checks are essential. Missing marks, final forms, spacing and coverage are blockers. The named implementations are not cleared below; S16 reservations and font guard apply. More preparation than stage 1. |
| 2. Texture | Learn paper and ink texture from cleared PD scans using a small diffusion model; condition on a rendered text mask or generate background/ink texture patches and composite them through the exact original mask. ControlNet is one possible architecture, not a guarantee of preservation. | A hard compositing boundary can preserve the original mask and skeleton exactly, concentrating the experiment on texture. | Texture may be unrealistic, obscure strokes through contrast, or miss useful shape variation. Enforce exact mask geometry and readable contrast; apply the reader filter anyway. Recommended first. |
| 3. Line img2img | Low-noise img2img on each rendered line, with a text mask as conditioning and a strict character-level safety filter. | Can express subtle shape and texture changes together. | Noise and conditioning can change, delete or add letters and points. Low strength is not a safety guarantee; label rejection and paired retention are mandatory. Defer until a compliant checkpoint and level 2 are viable. |

A generated font is not automatically correct merely because its code points are assigned. For all levels, preserve logical-order UTF-8 NFC text and direction metadata; do not treat a pixel mask as proof of legibility.

## Licence and provenance gate

Only use components compatible with openly releasing CC0 training data and Apache-2.0 model weights. Audit code, checkpoints, training data, dependencies, fonts and source scans separately; a code licence does not establish a weight or output licence. Record exact version/hash, source, licence, notices and output/derivative terms before any run. Exclude non-commercial, unknown or incompatible terms until cleared; no external weights are silently relicensed.

- **First-run candidate:** a small unconditional DDPM trained from scratch on cleared PD texture crops, using [Hugging Face Diffusers](https://github.com/huggingface/diffusers/blob/main/LICENSE) (Apache-2.0 code). No pretrained weights, text encoder or ControlNet checkpoint. Train separate paper and ink texture distributions if ink crop volume supports it; otherwise keep original foreground and style only the paper. Model architecture, seed, training inputs and resulting weights must be recorded and cleared for Apache-2.0 release. This is a hypothesis, not a demonstrated useful Hebrew style model.
- [FontDiffuser](https://github.com/yeungchenwa/FontDiffuser) explicitly restricts its repository to non-commercial research: **exclude** its code and checkpoint. [DG-Font](https://github.com/ecnuycxie/DG-Font) has no identified repository licence via GitHub's licence metadata; checkpoint terms also need verification: **exclude pending explicit compatible licences**. These papers describe approaches, not permission to reuse implementations.
- [Stable Diffusion v1-4](https://huggingface.co/CompVis/stable-diffusion-v1-4) uses CreativeML OpenRAIL-M and [ControlNet v1.1 Canny](https://huggingface.co/lllyasviel/control_v11p_sd15_canny) is tagged OpenRAIL: **exclude from this Apache-weights pilot**. A permissive architecture does not clear its checkpoint or base model. [Google DDPM CIFAR-10](https://huggingface.co/google/ddpm-cifar10-32) is tagged Apache-2.0, but is a 32×32 natural-image model, not a validated print-texture or Hebrew model; do not substitute it without provenance and suitability review.
- A PD source alone does not prove every scan, font, input text, or transformation is CC0-compatible. Record jurisdiction and rights basis, scanner and any separate terms; avoid sources with unresolved restrictions. Release only after the separate publication approval and full provenance review.

## Sources and separation

Ask eval, via the lead, to clear candidate public-domain IA or Wikimedia Commons works and printer/source identifiers **before downloading or inspecting scans**. Obtain a recorded clearance against current evaluation reservations, including P-hist and S16 reservations v1–v7; never use reserved works or the held-out fonts Drugulin CLM and Simple CLM. No work is pre-cleared by this plan. Record work/edition, printer, year, source URL, scan rights and PD basis, chosen pages and crop hashes, and eval's clearance. Use only cleared training-source pages for style crops; keep real dev and registered held-out works disjoint by work, edition and printer where feasible, and document any shared printer explicitly. Eval performs overlap checks on the exact training text and source manifest and must return CLEAN for their hashes before training. Do not access test images, references or private evaluation material.

### Candidate editions for reservation clearance

The first run uses one edition and fits one paper texture distribution. Eval can clear all three IDs in one pass. Work, edition, imprint and duplicate-scan checks apply across repositories and mirrors. The Commons Public Domain Mark records a rights assessment. It is distinct from a CC0 dedication. Use the linked Commons file as the scan of record, and record its file revision and SHA-256 after clearance.

| Priority | Edition and imprint | Exact identifiers | Rights recorded in the catalog |
| --- | --- | --- | --- |
| 1 | Hahn's *Biblia Hebraica*, Leipzig, 1838. The IA catalog identifies C. Tauchnitz as printer and publisher. | IA `bibliahebraicaad00hahn`. Commons `File:Bibliahebraicaad00hahn.pdf`. | Commons PD-scan, PD-old and US public domain. [IA catalog](https://archive.org/details/bibliahebraicaad00hahn) · [Commons rights](https://commons.wikimedia.org/wiki/File:Bibliahebraicaad00hahn.pdf#Licensing) |
| 2 | Letteris Tanakh, first edition, Vienna, 1852. Verify exact printer and upstream scan terms before use. | IA `Tanakh_Letteris_1852`. Commons `File:Letteris Tanakh, 1st edition (Vienna, 1852) (IA Tanakh Letteris 1852).pdf`. Bibliographic ID `002093804`. | Commons PD-old-70 and US public domain, Public Domain Mark 1.0. [Commons provenance and rights](https://commons.wikimedia.org/wiki/File:Letteris_Tanakh,_1st_edition_(Vienna,_1852)_(IA_Tanakh_Letteris_1852).pdf#Licensing) |
| 3 | *Agudat Ezov* Haggadah, Vilna, 1903, Judah Leib Metz imprint. | Commons `File:Gavriel Zev Margolis. Agudat ezov. 1903.pdf`. Catalog aliases `10953`, `001300939`, OCLC `123020832`. | Commons PD-scan and US public domain, Public Domain Mark 1.0. [Commons imprint and rights](https://commons.wikimedia.org/wiki/File:Gavriel_Zev_Margolis._Agudat_ezov._1903.pdf#Licensing) |

After clearance, choose the first edition in this order with usable grayscale backgrounds. Sample up to 32 evenly spaced interior pages, excluding covers and inserts. Extract a target of 1,024 distinct 64×64 grayscale tiles from blank margins or wide intercolumn gaps at 300 dpi. Review each tile for ink, marks, identifying stamps, illustrations, clipping and scan borders. Require at least 512 suitable crops over at least 16 pages. If a cleared scan is effectively binary or fails coverage, proceed to the next cleared edition. Retain page IDs, crop rectangles, render settings and byte hashes in the input manifest. Hold the source choice fixed for both phases.

## Label safety and retention

For each generated line, retain its original text and mask; require two independently trained OCR readers, with distinct model provenance, to each match the entire label at character level after a fixed, documented normalization and RTL conversion. Preserve niqqud where present: do not strip marks or collapse confusable characters. Predeclare reader versions, decoding and normalization, and separately tabulate disagreements involving ה/ח, ד/ר, ב/כ, ו/י and ו/ז. A mismatch, missing output, extra character, ambiguity, mask alteration in level 2 or unreadable contrast rejects the line. Shared errors remain possible: inspect a blinded, stratified sample including all five pairs and marks, using an independent human reader; reject any identified drift and stop to revise the filter if the audit exposes systematic leakage. Record attempted, accepted and rejected counts and rejection rate, reasons and pair-specific rates as **data quality**, not OCR performance. No synthetic accuracy or model performance results are published.

## Controlled ablation and evaluation

Before training, register sources, exact lists and hashes, label normalization, baseline, transform parameters, seed(s), sample size, training budget, selection rule and scorer with eval. Generate transformed candidates from the same original lines; after filtering, use the identical accepted line IDs, labels, ordering, replay mix, initialization, hyperparameters and training steps in both arms. The only treatment is the transform; retain unchanged images for the control. A high or selective rejection rate limits the population the experiment represents: report it and stop if there are insufficient diverse accepted lines rather than cherry-picking. Use the same frozen readers and filter for every candidate, without consulting held-out data.

Select transform settings and checkpoints on **real dev data only**, through eval; no dev figures or outcomes are reported publicly. Freeze one candidate and its matched control and register the one comparison and primary metric before test access. Ask eval to score the pair once on a registered real held-out set, ideally P-hist, using its preregistered scorer, paired CER difference and book/page-aware confidence interval; report the held-out result even if negative. P-hist references and the registered default-model study are pending: use it only if eval confirms availability and permits this distinct registered use; otherwise wait or register another suitable real held-out set. Eval owns the data and scoring. No synthetic evaluation, test-driven iteration, or multiple held-out peeks. If feasibility or clearance fails, stop with no performance claim.

## Stage 1 job specification

The first job produces paper textures and paired inputs. A second job trains the two OCR arms once the feasibility output and real-dev protocol are accepted. Both use the same stage 1 budget. The job entry points below are implementation interfaces. Before launch, the staged scripts need a local fixture smoke, source clearance, final input hashes and lead approval to spend.

### GPU job and outputs

Use one secure-cloud RTX 4090, 24 GB, 60 GB ephemeral container disk and no persistent volume. Use the GPU profile's `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` image and pin its digest and the job's dependencies in the staged manifest. Use the current guarded runner interface at the reviewed [heocr-compute revision](https://github.com/HeOCR/heocr-compute/tree/2b583aebdc191971953d44c99e3b7dc09d990378). The staged root contains `level2.sh`, the source and render manifests, clean crops, line PNGs and labels, the two reader artifacts, the pinned model and dependency configuration, and the CLEAR/CLEAN attestations. Give each entry a SHA-256 via `heocr-remote manifest`. Only allowlisted open materials go to the pod. Do not upload any dev or test assets or credentials.

| Step | Fixed first-run configuration |
| --- | --- |
| Train paper model | Scratch 1-channel DDPM, 64×64, three U-Net widths 32/64/128, batch 32, AdamW at 0.0002 with noise-prediction MSE, 1,000 diffusion timesteps, seed 20261121, at most 30,000 steps and a 4-hour training cutoff. Save the last completed weights as safetensors. |
| Synthesize paper | Draw 128 deterministic 64×64 tiles with DDIM at 50 steps. Use reflection and 16-pixel overlap with linear blending. Limit background-only intensity changes to ±12 gray levels relative to a fixed background of 243. Apply the same rule on every line. |
| Lock the glyphs | Render with preset `none`. Derive alpha as `255 - render_gray`. Composite neutral paper for controls and generated paper for treatment only where alpha equals zero. Keep every pixel with alpha greater than zero identical across arms, with unchanged dimensions. Verify pixel equality on protected support and exact geometry by hash. Treat the unchanged preset render as the source of the ink pixels and neutralize its fully transparent background identically in both arms before applying the treatment. |
| Filter pairs | Require exact label agreement from Tesseract 5.5.3 with stock `tessdata_best/heb`, using `--oem 1 --psm 13`, and an [independently trained Hebrew ONNX line recognizer](https://huggingface.co/Rivok/paddleocr-hebrew/tree/c6bfad5d207024ef66927dd5d061308cb407a496), using `server-svtrv2` in line mode at the linked weight revision and [pinned decoder code](https://github.com/RivoksLab/paddleocr-hebrew/tree/3baae91ad6479ef0473f901b4ed96366ae6c1670). Freeze the stock model hash and both decoders before running. Verify logical order, character coverage and negative controls on authored fixtures. Both readers must match on both images. Apply NFC and whitespace collapse only. This first pilot uses unpointed input because the two readers have limited niqqud coverage. Stop if the reader contract or coverage fails. |
| Return and audit | Return weights, tile bytes with hashes in JSONL, the input and output manifests, separate paired `.lstmf` files, accepted IDs and rejection counts, job log and version metadata. Keep logs free of source text or personal information. Use the tile export and original images to reproduce a locally reviewed montage for the blinded label audit. Preserve the results only after verified pull and teardown. |

Expected duration exceeds 30 minutes. Tell the lead before queueing. After the source and text clearance and lead's spend OK, use the following invocation. `STAGE` must point to the staged, policy-approved input root's parent. Before running, verify the live quote and use the checkout whose behavior was checked.

```sh
heocr-remote manifest "$STAGE/in" -o "$STAGE/inputs.json"
heocr-remote run --profile gpu --hours 6 --run-cap 6.33 \
  --max-upload-gb 1 --max-pull-gb 0.5 \
  --manifest "$STAGE/inputs.json" --root "$STAGE/in" \
  --cmd 'bash in/level2.sh' --dry-run
```

Remove `--dry-run` only for the approved, attended launch. Confirm `dead-man's switch: armed` in the unbuffered runner output. The generic runner warns and continues if arming fails. Supervise from pod creation and interrupt immediately on an unavailable timer, then confirm pod termination. The job entry point must also fail closed before training unless it can arm the runner's pod-side timer. The documented fallback is runner teardown and sweep after confirmed orphaning. Do not create a second pod while any reservation remains unresolved.

### Matched training lists and dev selection

Prepare 1,000 unpointed lines using the public [CC0 text release `knesset-laws-v2`](https://github.com/HeOCR/htext/releases/tag/knesset-laws-v2), plain-lines asset SHA-256 `790099a2e64c2e391957a2c9f306c6a8c0addd087cfd8431666165f5b4f65de1`. Use this shared text to isolate the image intervention. Its modern legal register limits how well the pilot represents historical training text. Its source is an OCR layer. Review the chosen lines for transcription errors and identifying details before using them as labels. Skip errors and use the next eligible row in the seeded ordering. Use logical NFC and collapse whitespace. Keep unique 20–60-character lines made of Hebrew letters, spaces and sentence punctuation supported by both readers and the baseline. Exclude digits, abbreviations, niqqud, cantillation and lines with personal data. Use the asset line index for provenance. Rank via `sha256("20261121:" + NFC_text)` and freeze the first 1,000 eligible lines after review. Give each row an ID from the text hash. Have eval confirm CLEAN on the exact labels after this step and on any changed list.

Use the [governed line renderer](../line_render.md) at `2a566631483c2ed019d93319f90e408c1507df11`, seed 20261121, preset `none`, Frank Ruhl Libre and David Libre Regular under OFL-1.1, and ink band 27–34 px. Pin the renderer and font manifest hashes and build the clean PNGs once. The renderer's font guard must pass. Use stock `heb`'s supported character set in both arms. For each accepted ID produce two `lstm.train` encodings with the same label using Tesseract 5.5.3 and RTL code-point conversion. Reject the entire pair on a parse, filter or encoding failure. Audit a blinded 50-pair sample, with each confusable group represented, and stop on drift. Proceed only if at least 500 pairs remain, both fonts are represented and both members of all five confusable groups remain present. Keep rejected IDs as the denominator for the quality report.

| File | Training inputs |
| --- | --- |
| `control.list` | Original protected-ink images on constant gray paper, one `.lstmf` per accepted ID. |
| `texture.list` | The same accepted IDs and labels on generated paper, in the same seeded order. |

Freeze an ordered pair manifest with each label hash, both image and `.lstmf` hashes, and normalized list hashes. Verify order, count and labels are identical before training. Use stock `tessdata_best/heb` as the common starter and a pinned Tesseract 5.5.3 build, learning-rate reset at `1e-4`, no replay, one thread per arm and matched snapshots after 1, 2 and 3 list passes. Set the same fixed maximum iteration count from the accepted list length and retain both models at each scheduled count. Use the CPU profile on one pod for both arms and abort the pair if either arm cannot complete the same schedule. The CPU job stages only approved training inputs and writes both arms' traineddata, list hashes and logs to `out/`. In `train-pair.sh`, resolve each arm’s separate `.lstmf` paths under `/heocr/in` and assert that the stored hashes match the frozen manifest. Stop both arms if the same iteration budget cannot be reached inside the wall limit. Use this preflight under the same timer and termination checks as the GPU job.

```sh
heocr-remote manifest "$PAIR/in" -o "$PAIR/inputs.json"
heocr-remote run --profile cpu --hours 4 --run-cap 4.71 \
  --max-upload-gb 1 --max-pull-gb 0.5 \
  --manifest "$PAIR/inputs.json" --root "$PAIR/in" \
  --cmd 'bash in/train-pair.sh' --dry-run
```

Select **one common snapshot iteration** for the paired comparison on **P-hist audit2 real dev** (13 books). Eval runs the page OCR recipe in the [P-hist v1 registration](../../experiments/phist_v1/REGISTRATION.md), using Tesseract `--psm 3`, micro page CER and `line_fold_v1`. Choose the lowest texture-arm dev CER, with the earlier iteration breaking ties, and keep the control from that same iteration. Report the selected iteration and publish no dev metric. P-hist held-out scoring remains a separate registered handoff to eval.

### Worst-case budget

Use one GPU launch and at most one CPU launch. The runner quotes compute plus disk for wall time plus 15 minutes, rejects an over-cap quote before provisioning, and terminates on completion or error. This budget also allows up to the runner's 5% accepted compute price drift and minute rounding. Use no paid API, network volumes or automatic retry policy. Include any retained reservation in the spend total. Recheck the quote, actual charges and remaining stage budget before the CPU run.

| Job | Limit and accepted tariff | Worst case with drift, disk and billing rounding | Allocation |
| --- | --- | --- | --- |
| GPU texture and paired-list feasibility | 6 h wall time, 15 min allowance, at most $1.00/h compute, 60 GB disk at $0.012/h, `--run-cap 6.33` | $6.66 | $8 |
| CPU matched OCR arms | 4 h wall time, 15 min allowance, at most $1.10/h compute, 40 GB disk at $0.008/h, `--run-cap 4.71` | $4.97 | $6 |
| Stage contingency for teardown or billing variation | Keep unallocated and count all spend against the cap. | $6 available | $6 |
| Stage 1 ceiling | Confirm remaining budget and the lead's OK for each launch. | $11.63 planned maximum across both jobs | **$20** |

[RunPod's published RTX 4090 price](https://www.runpod.io/gpu-models/rtx-4090) is $0.89/h on Secure Cloud at planning time. The live provider quote and the project's balance and monthly limit govern any launch. If the first run fails, return the reason and actual spend for a lead decision. Keep the GPU tooling outside the baseline package and record the command, source and reader hashes, result hashes and ledger totals with the experiment.
