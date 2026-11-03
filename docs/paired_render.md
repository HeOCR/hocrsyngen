# Paired pre-photometric render

`hocrsyngen generate --emit-paired-render` writes `paired_render.json` and one
PNG per generated JPEG. Each PNG is the same composed page after the same
rotation and before blur, grain, contrast, brightness and JPEG encoding. It is
not a clean page: paper texture, stamps, lines and other occlusion remain. The
existing image, manifest, and opt-in line/region annotations are unchanged; the
annotations' final-page pixel frame applies to both images.

The optional `hocrsyngen_paired_render.v1` sidecar binds the exact manifest and
source JPEG hashes to relative PNG paths, PNG hashes, dimensions, generator
version, preset, and realized rotation, blur, grain, contrast, brightness and
JPEG-quality settings. `hocrsyngen validate` checks the sidecar when present,
including complete page coverage, safe paths, hashes and PNG dimensions. Hashes
bind bytes and metadata but do not authenticate a producer or prove visual
quality. Do not treat the two images as independent samples or a clean-gold
benchmark; they are a controlled comparison of the photometric pipeline and
encoding on the same synthetic composition. Exact bytes can vary across image
libraries and platforms. Existing batches and default generation do not gain
paired assets.
