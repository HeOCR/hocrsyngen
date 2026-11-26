# SPDX-License-Identifier: CC0-1.0
"""Generate synthetic oblique phone candidates from pinned TRAIN page rasters.

SDXL supplies only a smooth illumination ratio sampled on open paper. The
camera raster and its projected polygons remain the source of text and geometry.
"""
from argparse import ArgumentParser
from dataclasses import asdict
from hashlib import file_digest, sha256
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import traceback
import unicodedata

import cv2 as cv
import numpy as np
from PIL import Image

from experiments.capture3d import batch
from experiments.capture3d.developable import paper_model
from experiments.capture3d.review import projection_map
from .paper_effects import Crease, CreaseWarp, ShadowBand, cast_shadow, paper_texture, tone
from .paper_scene import _normalized_blur, encode, halo_residual, ink_layers, inked_albedo, linear

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
REVISION = "462165984030d82259a11f4367a4eed129e94a7b"
CONDITION_SIZE = (576, 768)
CAMERA_SIZE = (1536, 2048)
SEED = 190262
STEPS = 18
STRENGTH = .28
GUIDANCE = 4.4
NEGATIVE = ("text, writing, typography, numbers, logo, markings, people, watermark,"
            " changed perspective, hard glare, plastic paper, glossy reflections")
PROMPTS = (
    "diffuse window daylight on a matte sheet on wood, slight cool ambient bounce",
    "daylight on unprinted matte paper on pale concrete with a cool reflection",
    "an unprinted matte book beneath a broad window, warm reflected desk light",
    "unprinted cream paper under side daylight and soft warm tabletop reflection",
)


class Rejected(ValueError):
    pass


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def check(path, digest):
    if sha(path) != digest:
        raise ValueError(f"Changed bytes: {path.name}")
    return path


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def text_sha(value):
    return sha256(value.encode()).hexdigest()


def page_alpha(row, size):
    mx, my = projection_map(paper_model(row["paper"]), row["clip_from_sheet"],
                           (315, 445), size, row["phone"]["k1"])
    perimeter = lambda a: np.concatenate((a[0],a[:,-1],a[-1,::-1],a[::-1,0]))
    polygon = np.column_stack((perimeter(mx),perimeter(my)))
    mask = np.zeros(size[::-1],np.uint8)
    cv.fillPoly(mask,[np.rint(polygon*16).astype(np.int32)],255,lineType=cv.LINE_AA,shift=4)
    return mask.astype(np.float32)/255


def annotated_mask(row, size, whole_size):
    mask = np.zeros(size[::-1],np.uint8)
    scale = np.asarray(size)/whole_size
    for line in row["annotations"]:
        cv.fillPoly(mask,[np.rint(np.asarray(line["polygon"])*scale).astype(np.int32)],255)
    return cv.dilate(mask,cv.getStructuringElement(cv.MORPH_ELLIPSE,(7,7)))


def lighting(native, condition, donor, alpha, excluded):
    """Estimate a smooth RGB gain only on the new, unprinted synthetic plate."""
    blank = linear(condition)
    edit = linear(donor)
    ratio = np.log(np.clip((edit+.065)/(blank+.065), .66, 1.53))
    paper = cv.resize(alpha,CONDITION_SIZE,interpolation=cv.INTER_AREA)
    valid = (paper > .999) & (excluded == 0) & (condition.min(axis=2) > 80)
    if np.count_nonzero(valid) < 1000:
        raise ValueError("Too little open synthetic paper for estimating light")
    fallback = np.median(ratio[valid],axis=0)
    gain = np.exp(cv.resize(_normalized_blur(ratio,valid,27,fallback),
                             native.shape[1::-1],interpolation=cv.INTER_LINEAR))
    stock, ink = ink_layers(native)
    return encode(inked_albedo(stock,ink,gain)), gain, int(valid.sum())


def reader_quad(vertices):
    """Use a tight rotated frame for sampled polygons crossing a curved fold."""
    polygon = np.float32(vertices)
    if len(polygon) == 4:
        return polygon
    rectangle = cv.boxPoints(cv.minAreaRect(polygon))
    first_edge = np.linalg.norm(rectangle[1] - rectangle[0])
    second_edge = np.linalg.norm(rectangle[2] - rectangle[1])
    if second_edge > first_edge:
        rectangle = np.roll(rectangle, -1, axis=0)
    if rectangle[0, 0] > rectangle[1, 0]:
        rectangle = np.roll(rectangle, 2, axis=0)
    return rectangle


def line_strip(image, units):
    strips = []
    for unit in units:
        polygon = reader_quad(unit["polygon_px"])
        x0, y0 = np.floor(polygon.min(axis=0)).astype(int) - 3
        x1, y1 = np.ceil(polygon.max(axis=0)).astype(int) + 4
        if x0 < 0 or y0 < 0 or x1 > image.shape[1] or y1 > image.shape[0]:
            raise Rejected("line_alignment_margin")
        a, b, c, d = polygon - [x0, y0]
        height = (np.linalg.norm(a-d) + np.linalg.norm(b-c)) / 2
        width = (np.linalg.norm(a-b) + np.linalg.norm(c-d)) / 2
        if height < 2.3 or width < 3:
            raise Rejected("line_sampling")
        cols = max(12, int(min(1950, width * 34 / height)))
        dest = np.float32([[2, 2], [cols-3, 2], [cols-3, 35], [2, 35]])
        matrix = cv.getPerspectiveTransform(np.float32([a,b,c,d]), dest)
        patch = cv.warpPerspective(image[y0:y1, x0:x1], matrix, (cols, 38), flags=cv.INTER_LINEAR,
                                   borderMode=cv.BORDER_REPLICATE)
        gray = cv.cvtColor(patch, cv.COLOR_RGB2GRAY)
        paper = cv.morphologyEx(gray, cv.MORPH_CLOSE, np.ones((13, 27), np.uint8))
        ink = np.maximum(cv.subtract(paper, gray).astype(np.float32) - 4, 0)
        scale = max(24, np.quantile(ink, .98))
        strips.append(np.uint8(np.clip(255 - ink * 255 / scale, 0, 255)))
    width = max(strip.shape[1] for strip in strips) + 24
    sheet = np.full((49 * len(strips) + 16, width), 255, dtype=np.uint8)
    for index, strip in enumerate(strips):
        offset = width - strip.shape[1] - 12
        sheet[index*49+8:index*49+46, offset:width-12] = strip
    return sheet


def normalized(text):
    return "".join(char for char in unicodedata.normalize("NFC", text)
                   if not char.isspace() and unicodedata.category(char) != "Cf")


def reader(sheet, units):
    success, encoded = cv.imencode(".png", sheet)
    if not success:
        raise RuntimeError("Unable to encode OCR strip")
    read = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", "heb+eng", "--psm", "6"],
        input=encoded.tobytes(), check=True, capture_output=True, timeout=35,
        env=dict(os.environ, OMP_THREAD_LIMIT="1"),
    ).stdout.decode()
    target = normalized("\n".join(unit["text"] for unit in units))
    recognized = normalized(read)
    score = SequenceMatcher(None, target, recognized, autojunk=False).ratio()
    return {"recognition_sha256": sha256(recognized.encode()).hexdigest(),
            "reference_sha256": sha256(target.encode()).hexdigest(), "literal_similarity": score,
            "recognized_chars": len(recognized), "reference_chars": len(target)}


def project_lines(rows, warp):
    if warp is None:
        return rows,0.
    out, error = [], 0.
    for row in rows:
        poly = np.asarray(row["polygon_px"])
        followed = np.roll(poly,-1,axis=0)
        perimeter = np.concatenate([np.linspace(a,b,max(2,round(np.linalg.norm(b-a)/8)),endpoint=False)
                                     for a,b in zip(poly,followed,strict=True)])
        new = warp.forward(perimeter-.5)
        error = max(error,float(np.linalg.norm(warp.inverse(new) - perimeter + .5,axis=1).max()))
        out.append(row | {"polygon_px":(new+.5).tolist()})
    if error >= 1:
        raise Rejected("Line reprojected beyond a pixel")
    return out,error


def ensure_visible(lines,size):
    for row in lines:
        p = np.asarray(row["polygon_px"])
        if (p.min(axis=0) < 4).any() or (p.max(axis=0) > np.asarray(size)-5).any():
            raise Rejected("Text leaves the candidate frame")


def glyph_mask(native, alpha, lines):
    luma = cv.cvtColor(native,cv.COLOR_RGB2GRAY)
    paper = cv.morphologyEx(luma,cv.MORPH_CLOSE,np.ones((11,13),np.uint8))
    expected = np.zeros(luma.shape,np.uint8)
    for line in lines:
        cv.fillPoly(expected,[np.rint(line["polygon_px"]).astype(np.int32)],1)
    glyphs = (paper.astype(np.int16)-luma > 18) & (expected > 0)
    return glyphs, (alpha>.99) & (paper>95)


def shadow_readback(final, base, alpha, lines, coverage):
    ink,paper = glyph_mask(base,alpha,lines)
    before,after = [cv.cvtColor(rgb,cv.COLOR_RGB2GRAY) for rgb in (base,final)]
    gain = linear(after)/np.maximum(linear(before),.001)
    dark,lit = coverage >= .95,coverage <= .05
    far = cv.distanceTransform(1-ink.astype(np.uint8),cv.DIST_L2,cv.DIST_MASK_PRECISE) >= 10
    answer = {}
    for name,mask in (("ink",ink & paper & (before>33)),("paper",paper & far)):
        shaded,sun = gain[mask & dark],gain[mask & lit]
        if min(shaded.size,sun.size) < 300:
            raise Rejected("Shadow misses ink or blank paper")
        shaded_m,sun_m = float(np.median(shaded)),float(np.median(sun))
        if shaded_m >= .65 or shaded_m/sun_m >= .67:
            raise Rejected(f"Insufficient shadow attenuation on {name}")
        answer[name] = {"shade_gain":shaded_m,"lit_gain":sun_m,"shade_pixels":int(shaded.size)}
    crossed = 0
    for line in lines:
        pts = np.rint(line["polygon_px"]).astype(np.int32)
        x,y,w,h = cv.boundingRect(pts)
        patch = np.zeros((h,w),np.uint8)
        cv.fillPoly(patch,[pts-np.array([x,y],np.int32)],1)
        region = np.s_[y:y+h,x:x+w]
        inside = ink[region] & (patch > 0)
        crossed += bool(np.count_nonzero(inside & lit[region]) >= 8 and np.count_nonzero(inside & dark[region]) >= 8)
    if crossed < 2:
        raise Rejected("Hard shadow must cross at least two literal printed lines")
    answer["crossed_lines"] = crossed
    return answer


def read_halo(final, matched, alpha, rows):
    ink,paper = glyph_mask(matched,alpha,rows)
    result = halo_residual(final,matched,ink,paper)
    if abs(result["ring_minus_open"]) >= 2 or result["p95_abs"] >= 3.8:
        raise Rejected(f"Halo discipline failed: {result}")
    return result


def load_model(weights, offline):
    import diffusers
    from diffusers import StableDiffusionXLImg2ImgPipeline
    from huggingface_hub import snapshot_download
    import torch

    if weights["model"] != MODEL or weights["revision"] != REVISION:
        raise ValueError("A different SDXL revision was specified")
    if not torch.cuda.is_available():
        raise RuntimeError("The scale job needs a CUDA GPU")
    path = Path(snapshot_download(MODEL, revision=REVISION, local_files_only=offline,
                                  allow_patterns=[r["path"] for r in weights["files"]]))
    for r in weights["files"]:
        if check(path/r["path"], r["sha256"]).stat().st_size != r["bytes"]:
            raise ValueError("SDXL component length mismatch")
    torch.set_num_threads(1)
    model = StableDiffusionXLImg2ImgPipeline.from_pretrained(
        path, variant="fp16", local_files_only=True, torch_dtype=torch.float16,
        use_safetensors=True).to("cuda")
    model.vae.to(dtype=torch.float32)
    model.set_progress_bar_config(disable=True)
    return model, {"cuda":torch.version.cuda,"torch":torch.__version__,
                   "diffusers":diffusers.__version__,"vae_dtype":"float32",
                   "gpu":torch.cuda.get_device_name()}


def scene_config(number, attempt):
    """Authored optics vary by page and retry. No photo-derived parameter file."""
    rng = np.random.default_rng(SEED + number*8191 + attempt*98317)
    lane = number % 4
    scene = ("desk","floor","book","letter")[lane]
    sign = (1, -1, 1, -1)[lane]
    if attempt:
        lateral = rng.uniform(.14,.18)
        distance = rng.uniform(.31,.34)
    else:
        lateral = rng.uniform(.155,.205)
        distance = rng.uniform(.29,.325)
    pose = {"offset_m":[float(rng.uniform(-.038,.038)),float(sign*lateral),float(distance)],
            "roll_deg":float(rng.uniform(-3.4,3.4)),"lens_mm_equivalent":float(rng.uniform(27,30))}
    return scene, pose


def effect_config(index, attempt, lines, size):
    rng = np.random.default_rng(SEED + index*919 + 137)
    w = min(size)
    center = np.median(np.concatenate([r["polygon_px"] for r in lines]),axis=0)
    x,y = center
    bands, folds, ambient, texture = [], [], None, 0.
    lane = int(rng.integers(20))
    # Reject-specific retries reduce the effect count, keeping the SDXL pass.
    if attempt > 1:
        return bands, ambient, folds, texture, lane
    if lane in range(3,9):
        strength = float(rng.uniform(.35,.50))
        ambient = (strength,strength+.04,strength+.10)
        angle = float(rng.choice([-53,70,77]))
        bands.append(ShadowBand((x+.13*w,y),angle,6,.032*w))
        if lane in (5,6) and not attempt:
            bands.append(ShadowBand((x-.15*w,y-.06*w),angle,6,.025*w))
    if lane in range(6,14):
        texture = float(rng.uniform(.48,.81))
    if lane in (6,9,10,11,12) and not attempt:
        folds.append(Crease((x-.075*w,y+.12*w),float(rng.uniform(-20,20)),.032*w,.225,.37))
    return bands,ambient,folds,texture,lane


def synthesize(native, camera, row, model, attempt):
    import torch

    index = row["ordinal"]
    size = native.shape[1::-1]
    mask = page_alpha(camera,size)
    text_region = annotated_mask(camera,CONDITION_SIZE,size)
    reduced = cv.resize(native,CONDITION_SIZE,interpolation=cv.INTER_AREA)
    blank = cv.inpaint(reduced,text_region,7,cv.INPAINT_TELEA)
    prompt = ("Natural oblique phone photo of a blank paper surface, keep framing and folds. "
              + PROMPTS[index%len(PROMPTS)] + ".")
    seed = SEED + index*317 + attempt*1000003
    with torch.inference_mode():
        proposed = model(prompt, negative_prompt=NEGATIVE, image=Image.fromarray(blank),
                         num_inference_steps=STEPS, strength=STRENGTH, guidance_scale=GUIDANCE,
                         generator=torch.Generator(device="cpu").manual_seed(seed)).images[0]
    donor = np.asarray(proposed.convert("RGB"))
    if donor.max()<32:
        raise Rejected("invalid_sdxl_donor")
    relit,gain,opened = lighting(native,blank,donor,mask,text_region)
    p10,p90 = np.quantile(gain[mask>.99],[.10,.90])
    if p90-p10 < .05:
        raise Rejected("low_sdxl_illumination_variation")
    lines = [{"id":a["id"],"text":a["text"],"polygon_px":a["polygon"]} for a in camera["annotations"]]
    ensure_visible(lines,size)
    source = row["page"]["annotations"]
    if [(a["id"],a["text"]) for a in lines] != [(a["id"],a["text"]) for a in source]:
        raise RuntimeError("Ordered TRAIN labels changed during camera projection")
    source_halo = read_halo(relit,native,mask,lines)
    bands,amb,folds,tex,lane = effect_config(index,attempt,lines,size)
    warp = CreaseWarp(mask,folds) if folds else None
    moved,max_project = project_lines(lines,warp)
    ensure_visible(moved,size)
    base = warp.remap(relit) if warp else relit
    fold_light = warp.illumination[...,None] if warp else 1.
    shadow,coverage = cast_shadow(size,bands,amb) if bands else (1.,None)
    texture = 1.
    motifs = []
    if tex:
        texture,motifs = paper_texture(mask,seed,tex)
        if warp:
            texture = warp.remap(texture)
    illumination = fold_light*shadow
    final = tone(base,illumination*texture)
    halo = read_halo(tone(final,1/illumination),base,mask,moved)
    b = reader(line_strip(native,lines),lines)
    a = reader(line_strip(warp.rectify(final) if warp else final,lines),lines)
    if a["literal_similarity"] < .56 or a["literal_similarity"] < b["literal_similarity"]-.065:
        raise Rejected("paired_reader_drift")
    shade = shadow_readback(final,base,mask,moved,coverage) if bands else None
    proof = {
        "seed":seed,"prompt":prompt,"condition_rgb_sha256":sha256(blank.tobytes()).hexdigest(),
        "donor_rgb_sha256":sha256(donor.tobytes()).hexdigest(),"gain_p10_p90":[float(p10),float(p90)],
        "gain_open_paper_pixels":opened,"fresh_sdxl_halo":source_halo,"halo":halo,
        "max_reprojection_px":max(camera["marker_check"]["max_px"],max_project),
        "paired_reader":{"new_camera":b,"final":a},"cast_shadow":shade,
        "shadow_bands":[asdict(band) for band in bands],"ambient_linear_rgb":amb,
        "crease_warps":[asdict(fold) for fold in folds],"paper_texture":tex,"stains":motifs,"lane":lane,
        "capture_recipe": {k:camera[k] for k in ("scene","camera_pose","paper","phone","clip_from_sheet","marker_check")},
        "cached_sdxl_edits":[],"fitted_photo_profiles":[],
    }
    return final,moved,proof


def camera_batch(rows, source, scratch, assets, blender, device, attempt, guard_hash, samples):
    """Only signed native TRAIN pixels enter the new camera batch."""
    scratch.mkdir()
    entries, folds = [], []
    roster_path = scratch/"camera-input.json"
    for row in rows:
        entry = row["page"].copy()
        check(source/entry["image"],entry["sha256"])
        entry["image"] = f"native/{Path(entry['image']).name}"
        index = row["ordinal"]
        scene,pose = scene_config(index,attempt)
        entry.update(scene=scene,camera_pose=pose,seed=SEED+index*631+attempt*731)
        entries.append(entry)
        if index % 12 in (3,7):
            folds.append(f"{entry['id']}={'parallel' if index%3 else 'half'}")
    # The renderer confines media to its source root.
    (scratch/"native").mkdir()
    for entry in entries:
        name = entry["image"]
        shutil.copyfile(source/"pages"/Path(name).name,scratch/name)
    write(roster_path,{"split":"train-calibration","text_gate_sha256":sha(source/"roster.json"),
                       "fonts_guard_sha256":guard_hash,"pages":entries})
    batch.run(roster_path,assets,scratch/"capture",blender,device,CAMERA_SIZE,samples,
              .65,realism_seed=SEED,developable_paper=True,rounded_fold=folds,clean_arm_only=True)
    output = read(scratch/"capture/generation_manifest.json")
    if "photometry_profile_sha256" in output or "frozen_v2_optics_sha256" in output:
        raise RuntimeError("Unexpected fitted camera input")
    return {c["pair_id"]:c for c in output["renders"] if c["arm"]=="clean"},output["scene_assets"]


def emit(root, row, final, lines, recipe, asset_pins, model_lock, camera):
    source_id = row["page"]["id"]
    ident = f"sdxl-oblique-{source_id}"
    photo = f"images/{ident}.png"
    gt = f"layout/{ident}.json"
    Image.fromarray(final).save(root/photo,compress_level=3)
    pin = sha(root/photo)
    write(root/gt,{"schema":"heocr.scanifier_projected_lines.v1","id":ident,
                   "size_px":list(final.shape[1::-1]),"media_sha256":pin,
                   "lines":lines,"reading_order":[r["id"] for r in lines]})
    role = "floor" if camera["scene"]=="floor" else "desk"
    inherited = {
        "native_raster_sha256":row["page"]["sha256"],
        "parent_native_gt_sha256":row["parent"]["native_gt_sha256"],
        "native_font_pins":row["parent"]["font_pins"],"print_pack_pdf":row["print_pack"],
        "cc0_scene_assets":{name:asset_pins[name] for name in (role,"environment")},
        "pretrained_model_lock_sha256":model_lock,"pretrained_sdxl":f"{MODEL}@{REVISION}",
        "cached_sdxl_edits":[],"fitted_photo_profiles":[],
    }
    row_result = {
        "id":ident,"ordinal":row["ordinal"],"source_id":source_id,"split":"train","view":"sdxl-oblique",
        "line_count":len(lines),"media":photo,"media_sha256":pin,"layout":gt,
        "layout_sha256":sha(root/gt),"fresh_camera_sha256":camera["image_sha256"],
        "parent":row["parent"],"lineage":inherited,"recipe":recipe,
        "page_text_sha256":text_sha(row["truth"]["text"]),"body_text_sha256":text_sha(row["truth"]["body_text"]),
    }
    write(root/f"rows/{row['ordinal']:04d}.json",row_result)
    return row_result


def main():
    args = ArgumentParser(description=__doc__)
    args.add_argument("source",type=Path)
    args.add_argument("output",type=Path)
    args.add_argument("--assets",required=True,type=Path)
    args.add_argument("--weights",required=True,type=Path)
    args.add_argument("--fonts-guard",required=True,type=Path)
    args.add_argument("--blender",required=True)
    args.add_argument("--device",default="OPTIX",choices=("OPTIX","CUDA"))
    args.add_argument("--batch-size",type=int,default=24)
    args.add_argument("--samples",type=int,default=12)
    args.add_argument("--deadline-seconds",type=int,required=True)
    args.add_argument("--requested-lines",type=int,required=True)
    args.add_argument("--offline",action="store_true")
    options = args.parse_args()
    started = time.monotonic()
    stop = started+options.deadline_seconds
    source = options.source.resolve()
    folder = options.output.resolve()
    for name in ("images","layout","rows","scratch"):
        (folder/name).mkdir(parents=True,exist_ok=True)
    cv.setNumThreads(1)
    roster = read(source/"roster.json")
    if roster["cached_sdxl_edits"] != [] or roster["fitted_photo_profiles"] != []:
        raise ValueError("The source roster must declare zero cached edits and fitted profiles")
    pages = roster["pages"]
    guard = read(options.fonts_guard)
    excluded_families = {entry["family"].casefold() for entry in guard["families"]}
    excluded_hashes = {file["sha256"] for entry in guard["families"] for file in entry["files"]}
    font_pins = [font for row in pages for font in row["parent"]["font_pins"]]
    families = {family.casefold() for row in pages for family in row["parent"]["font_families"]}
    if families & excluded_families or any(font["sha256"] in excluded_hashes for font in font_pins):
        raise ValueError("A reserved font entered the TRAIN roster")
    accepted, rejects = [], []
    model_hash = sha(options.weights)
    shutil.copyfile(options.weights,folder/"model-weights.json")
    model, runtime = load_model(read(options.weights), options.offline)
    target = options.requested_lines
    accepted_lines = 0
    failure = None
    try:
        for offset in range(0,len(pages),options.batch_size):
            current = pages[offset:offset+options.batch_size]
            for attempt in range(3):
                if not current or accepted_lines >= target or time.monotonic() > stop:
                    break
                scratch = folder/"scratch"/f"batch-{offset:04d}-{attempt}"
                try:
                    camera, scene_assets = camera_batch(current,source,scratch,options.assets,options.blender,
                                                        options.device,attempt,sha(options.fonts_guard),options.samples)
                except ValueError as exc:
                    if str(exc)!="Every render failed the frame or visibility threshold":
                        raise
                    camera = {}
                retry = []
                for row in current:
                    if time.monotonic()>stop or accepted_lines>=target:
                        break
                    shot = camera.get(row["page"]["id"])
                    if shot is None:
                        retry.append(row)
                        rejects.append([row["ordinal"],attempt,"camera_framing"])
                        continue
                    with Image.open(check(scratch/"capture"/shot["image"],shot["image_sha256"])) as plate:
                        native = np.asarray(plate.convert("RGB"))
                    try:
                        final, lines, proof = synthesize(native,shot,row,model,attempt)
                    except Rejected as exc:
                        retry.append(row)
                        rejects.append([row["ordinal"],attempt,str(exc)])
                        continue
                    proof["attempt"] = attempt
                    result = emit(folder,row,final,lines,proof,scene_assets,model_hash,shot)
                    accepted.append(result)
                    accepted_lines += len(lines)
                    print(f"{row['ordinal']} accepted, {accepted_lines}/{target} cumulative lines",flush=True)
                shutil.rmtree(scratch)
                current = retry
            if accepted_lines >= target or time.monotonic() > stop:
                break
    except Exception as exc:
        if not accepted:
            raise
        traceback.print_exc()
        failure = type(exc).__name__
        print(f"Sealing {len(accepted)} verified views after {failure}",flush=True)
    accepted.sort(key=lambda row:row["ordinal"])
    for row in accepted:
        check(folder/row["media"],row["media_sha256"])
        check(folder/row["layout"],row["layout_sha256"])
    admitted_files = {folder/row[key] for row in accepted for key in ("media","layout")}
    for dirname in ("images","layout"):
        for path in (folder/dirname).iterdir():
            if path not in admitted_files:
                path.unlink()
    with (folder/"inventory.jsonl").open("w") as handle:
        for entry in accepted:
            handle.write(json.dumps(entry,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n")
    write(folder/"generation_manifest.json",{
        "schema":"heocr.synthetic_oblique_sdxl_train.v1","source_roster_sha256":sha(source/"roster.json"),
        "input_fonts_guard_sha256":sha(options.fonts_guard),"cached_sdxl_edits":[],"fitted_photo_profiles":[],
        "request_lines":target,"views":len(accepted),"lines":accepted_lines,"runtime":runtime,
        "partial_failure":failure,
        "reason_counts":{reason:sum(row[2]==reason for row in rejects) for reason in sorted({r[2] for r in rejects})},
        "rejected_attempts":rejects,"model_weights_sha256":model_hash,"steps":STEPS,"strength":STRENGTH,
        "guidance":GUIDANCE,"negative_prompt":NEGATIVE,"camera_device":options.device,"camera_samples":options.samples,
        "camera_px":CAMERA_SIZE,"condition_px":CONDITION_SIZE,"source":f"pretrained-only {MODEL}@{REVISION}",
        "inventory_sha256":sha(folder/"inventory.jsonl"),"wall_seconds":time.monotonic()-started,
    })
    print(f"Finished {len(accepted)} pages, {accepted_lines} lines",flush=True)


if __name__ == "__main__":
    main()
