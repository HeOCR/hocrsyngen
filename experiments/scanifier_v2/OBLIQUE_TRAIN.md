# Scanifier capture recipe for modern print

Fit each endpoint on authorized non-test captures. Render fresh TRAIN pages with those parameters and use independent real phone captures for the recognizer comparison. Calibration photos, reference text and capture identifiers stay in their authorized custody.

| Effect | Fitted endpoint and application |
| --- | --- |
| Perspective and obliquity | Draw one complete geometry record in `render_fitted_phone_view`. Keep pose, optical scale, crop and the page warp together. Use the approved observed or reframed bank as registered. |
| Motion and defocus | The phone optical fit estimates effective spread and edge defocus from matched captures. The office scanner fit measures scan softness separately. |
| Uneven light and noise | Use the frame gradient, local shadow and spatial residual from the same fitted phone endpoint. The office profile uses its own tone curve and scanner residual. |
| Show-through | Use `render_training_view` with the matching duplex fit and an eligible, registered TRAIN verso. Apply before the endpoint's geometry or crop. Single-sided pages skip this step. |
| Black scanner fringe | Use the fitted scanner edge with protected line boxes. Reject a fringe that changes protected pixels. Interior bars are a separate renderer with no measured fit here. |
| JPEG and app delivery | Use the endpoint's camera/scanner JPEG replay. For a message-delivery view, apply `apply_jpeg_delivery` to the full rendered phone frame before cropping. |

The [print-pack protocol](calibration_pack/REGISTER.md) calls for an A camera frame and F copy of that frame sent through Telegram as a photo. For each authorized pair verify both capture hashes and that F came from the same upright A frame. `fit_jpeg_delivery` reads the observed output size, quantization tables and chroma sampling from F. The pair needs to show a downsample for the long-edge cap to be identifiable. Preserve the fit IDs in private provenance and draw an entire fit per view. This replays those observed JPEG settings with Pillow's LANCZOS resampling. App color processing and resampling kernels are outside the fit. Record delivery as unmeasured for a collection until an independently joined A/F pair is available, and keep its native camera JPEG endpoint eligible.

```python
from experiments.scanifier_v2.delivery import apply_jpeg_delivery, fit_jpeg_delivery
from experiments.scanifier_v2.phone_training import phone_line_crop, render_fitted_phone_view

view = render_fitted_phone_view(
    source, source_lines, optical_profile, pose_bank, seed=seed, long_edge=4080,
)
if delivery_pair is not None:
    fit = fit_jpeg_delivery(
        delivery_pair.original_bytes, delivery_pair.delivered_bytes,
        original_sha256=delivery_pair.original_sha256,
        delivered_sha256=delivery_pair.delivered_sha256,
    )
    view = apply_jpeg_delivery(view, source_lines, source.size, [fit], seed=seed)
crop, rejection = phone_line_crop(view, line_index)
```

The message-delivery step updates the camera matrix and recomputes boxes, baselines and sampling height. Reject underresolved, clipped and neighbor-contaminated crops after the final delivery stage. Store crops losslessly and preserve literal logical labels. Log the ordered source and layout hashes, fit hashes, seed, final image and crop hashes, geometry and any rejection. Keep clean witnesses outside the visit list.

## One recognizer arm

- Freeze 384 oblique phone and 128 office-scanner visits from eligible modern TRAIN renders. Use a native phone long edge of 4,080 px, an office endpoint at 300 ppi, seed-ranked parents and lines, one view per accepted label, and at most four selected lines per parent. These source pages are single-sided. Route documented duplex and edge overlays only to later eligible page families.
- Interleave those 512 visits with 512 published-source or project-authored TRAIN replay visits. Start from the same modern float baseline and codec as the control. Use a reset learning rate of `1e-6`, one fixed 1,024-visit terminal and zero skipped CTC lines. Keep the original label bytes. Bind the exact render, replay, native encoder, visit order, CLEAN, and remote-transfer scope before running on an autonomous pod capped at $3.
- Register one paired comparison on real, authorized oblique-phone DEV before fitting. Use identical masked positions, line geometry and scoring for the terminal and original baseline, with paired intervals clustered by source. Keep fixed real near-phone and issuer guards. Promote only with a favorable primary interval and no guard regression. Keep all DEV reads on the Mac. Report the internal verdict only after the registered comparison.
