# SPDX-License-Identifier: CC0-1.0
"""Blender 5.x entry point. Run with blender -b --python-exit-code 1 -P render.py -- JOB.json."""

from dataclasses import asdict
import json
import math
from pathlib import Path
import random
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry import Paper, distort
from developable import DevelopablePaper, from_capture
from paper_material import office_paper
from strong_folds import CrossCreasedPaper, design


SCENES = {
    "desk": {"curl": .006, "crumple": .0015},
    "floor": {"curl": .009, "crumple": .0035},
    "book": {"curl": .006, "spine": .031},
    "letter": {"curl": .007, "crease_height": .024, "crease_angle": .09, "crumple": .0025},
}


def use_cycles(device):
    preferences = bpy.context.preferences.addons["cycles"].preferences
    if device == "CPU":
        return "CPU"
    preferences.compute_device_type = device
    preferences.refresh_devices()
    names = []
    for item in preferences.devices:
        item.use = item.type == device
        if item.use:
            names.append(item.name)
    if not names:
        raise RuntimeError(f"No Cycles {device} device")
    return ", ".join(names)


def color_multiply(tree, source, rgb):
    tint = tree.nodes.new("ShaderNodeMixRGB")
    tint.blend_type = "MULTIPLY"
    tint.inputs[0].default_value = 1
    tint.inputs[2].default_value = (*rgb, 1)
    tree.links.new(source, tint.inputs[1])
    return tint.outputs[0]


def material(name, *, image=None, color=None, roughness=.55, emission=False):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    tree = result.node_tree
    output = tree.nodes.get("Material Output")
    if emission:
        shader = tree.nodes.new("ShaderNodeEmission")
        tree.links.new(shader.outputs[0], output.inputs[0])
        color_input = shader.inputs["Color"]
    else:
        shader = tree.nodes.get("Principled BSDF")
        shader.inputs["Roughness"].default_value = roughness
        color_input = shader.inputs["Base Color"]
    if image:
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(image), check_existing=True)
        if emission:
            node.interpolation = "Closest"
        source = node.outputs["Color"]
        if color is not None:
            source = color_multiply(tree, source, color)
        tree.links.new(source, color_input)
    else:
        color_input.default_value = (*color, 1)
    return result


def printed_specular(style):
    """Give absorbent ink a weaker reflection than the exposed paper stock."""
    tree = style.node_tree
    texture = next(node for node in tree.nodes if node.type == "TEX_IMAGE")
    response = tree.nodes.new("ShaderNodeRGBToBW")
    tree.links.new(texture.outputs["Color"], response.inputs[0])
    level = tree.nodes.new("ShaderNodeMath")
    level.operation = "MULTIPLY_ADD"
    level.inputs[1].default_value = .36
    level.inputs[2].default_value = .065
    tree.links.new(response.outputs[0], level.inputs[0])
    tree.links.new(level.outputs[0], tree.nodes.get("Principled BSDF").inputs["Specular IOR Level"])


def add_sheet(name, paper, style, *, x_offset=0, turn=False):
    points, faces, uvs = paper.mesh()
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points, [], faces)
    mesh.update()
    uv_map = mesh.uv_layers.new(name="Page UV")
    for loop in mesh.loops:
        uv_map.data[loop.index].uv = uvs[loop.vertex_index]
    for face in mesh.polygons:
        face.use_smooth = not isinstance(paper, CrossCreasedPaper)
    if isinstance(paper, DevelopablePaper):
        mesh.normals_split_custom_set_from_vertices([paper.normal(u, 1 - v) for u, v in uvs])
    sheet = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(sheet)
    sheet.location.x = x_offset
    if turn:
        sheet.rotation_euler.z = math.pi
    sheet.data.materials.append(style)
    solidify = sheet.modifiers.new("Paper caliper", "SOLIDIFY")
    solidify.thickness = paper.thickness
    solidify.offset = -1
    return sheet


def box(name, location, size, style, *, angle=0, bevel=.002):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=(0, 0, angle))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    edge = obj.modifiers.new("Rounded edges", "BEVEL")
    edge.width, edge.segments = bevel, 3
    obj.data.materials.append(style)
    return obj


def aim(obj, target):
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = (Vector(target) - obj.location).to_track_quat("-Z", "Y")


def light(name, kind, location, target, power, size, color=(1, 1, 1), spot_degrees=0):
    data = bpy.data.lights.new(name, kind)
    data.energy = power
    data.color = color
    if kind == "AREA":
        data.shape, data.size, data.size_y = "RECTANGLE", size, size * .58
    else:
        data.shadow_soft_size = size
    if kind == "SPOT":
        data.spot_size = math.radians(spot_degrees)
        data.spot_blend = .48
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)


def set_camera(scene, rng, mode, photo):
    data = bpy.data.cameras.new("Phone optics")
    camera = bpy.data.objects.new("Phone camera", data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    target = (.028, 0, .006) if mode == "book" else (0, 0, .006)
    base = Vector((rng.uniform(-.085, .085), rng.uniform(-.125, .12), rng.uniform(.305, .39)))
    if mode == "book":
        base.x += .05
        base.z += .055
    data.sensor_fit = "HORIZONTAL"
    data.sensor_width = 36
    data.lens = photo["lens_mm_equivalent"]
    data.clip_start = .015
    data.dof.use_dof = photo.get("defocus_enabled", True)
    data.dof.focus_distance = (Vector(target) - base).length + photo.get("focus_offset_m", 0)
    data.dof.aperture_fstop = photo["fstop_equivalent"]
    roll = Quaternion((0, 0, 1), math.radians(photo["roll_deg"]))
    directional_shake = "motion_angle_deg" in photo
    angle = math.radians(photo.get("motion_angle_deg", 0))
    motion = Vector((math.cos(angle), math.sin(angle) if directional_shake else -.45, 0)) * photo["shutter_drift_m"]
    for frame, displacement in ((0, -motion), (1, Vector((0, 0, 0))), (2, motion)):
        camera.location = base + displacement
        forward = (Vector(target) - (base if directional_shake else camera.location)).normalized()
        right = forward.cross(Vector((0, 1, 0))).normalized()
        up = right.cross(forward)
        camera.rotation_mode = "QUATERNION"
        camera.rotation_quaternion = Matrix((right, up, -forward)).transposed().to_quaternion() @ roll
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    scene.frame_set(1)
    scene.render.use_motion_blur = photo["shutter_drift_m"] > 0
    scene.render.motion_blur_shutter = .42
    scene.render.motion_blur_position = "CENTER"
    return camera


def scene_for(job, case, rng):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU" if job["device"] == "CPU" else "GPU"
    scene.cycles.samples = job["samples"]
    scene.cycles.seed = case["seed"]
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 5
    scene.render.resolution_x, scene.render.resolution_y = job["size"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.use_file_extension = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = rng.uniform(-.32, .30)

    mode = case["scene"]
    realism = case.get("realism")
    world = bpy.data.worlds.new("Interior environment")
    scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    environment = tree.nodes.new("ShaderNodeTexEnvironment")
    environment.image = bpy.data.images.load(job["assets"]["environment"], check_existing=True)
    background = tree.nodes.get("Background")
    environmental_color = environment.outputs["Color"]
    ambient_strength = .32 if mode == "floor" else .48
    if realism:
        scene_lighting = realism["lighting"]
        ambient_strength = scene_lighting["ambient_strength"]
        environmental_color = color_multiply(tree, environmental_color, scene_lighting["ambient_rgb"])
    background.inputs["Strength"].default_value = ambient_strength
    tree.links.new(environmental_color, background.inputs["Color"])
    bpy.ops.mesh.primitive_plane_add(size=1.22)
    support = bpy.context.object
    support.name = "Concrete floor" if mode == "floor" else "Oak tabletop"
    substrate = job["assets"]["floor" if mode == "floor" else "desk"]
    support.data.materials.append(material("Surface", image=substrate, roughness=.72))

    parameters = dict(SCENES[mode])
    source_width, source_height = case["source_size"]
    parameters["height"] = .210 * source_height / source_width
    parameters.update(phase=rng.uniform(0, 6.28), crease_u=rng.uniform(.4, .62))
    for key in ("curl", "crease_height", "crumple"):
        if key in parameters:
            parameters[key] *= rng.uniform(.78, 1.30)
    if realism:
        parameters.update(realism["fold"]["settings"])
    reference_paper = Paper(**parameters)
    matte_paper = job.get("developable_paper", False)
    paper = from_capture(reference_paper, mode, realism, case["seed"]) if matte_paper else reference_paper
    if strong_fold := case.get("strong_fold"):
        paper = design(paper, strong_fold, case["seed"])
    roughness = rng.uniform(.55, .73)
    stock = realism["paper"] if realism else {}
    if matte_paper:
        paper_style = office_paper("Matte office paper", paper, stock["reflectance_rgb"],
                                   ink=case["image"], showthrough=case["showthrough"])
    else:
        paper_style = material("Printed paper", image=case["image"], color=stock.get("reflectance_rgb"),
                               roughness=stock.get("roughness", roughness))
    if realism and not matte_paper:
        printed_specular(paper_style)
    elif not matte_paper:
        paper_style.node_tree.nodes.get("Principled BSDF").inputs["Specular IOR Level"].default_value = .20
    offset = .108 if mode == "book" else 0
    sheet = add_sheet("Printed sheet", paper, paper_style, x_offset=offset)
    if mode == "book":
        card = material("Facing paper", color=stock.get("reflectance_rgb", (.83, .77, .64)), roughness=.75)
        facing = Paper(width=paper.width, height=paper.height, curl=.006, spine=.031) if realism else paper
        if matte_paper:
            facing = from_capture(reference_paper, mode, realism, case["seed"], facing=True)
            face_style = office_paper("Matte facing leaf", facing, stock["reflectance_rgb"])
        else:
            face_style = card
        add_sheet("Facing leaf", facing, face_style, x_offset=-offset, turn=True)
        binding = material("Cloth book cover", color=(.09, .034, .017))
        box("Binding", (0, 0, -.002), (.438, .307, .005), binding)
        box("Leaf block", (0, 0, .00025), (.428, .297, .001), card, bevel=.001)
    elif mode == "desk":
        cloth = material("Notebook cover", color=(.048, .08, .092))
        box("Notebook", (-.178, .119, .005), (.085, .134, .010), cloth, angle=-.21)
        graphite = material("Pencil", color=(.25, .105, .021), roughness=.42)
        box("Pencil", (.154, .015, .003), (.007, .143, .006), graphite, angle=-.30, bevel=.001)
    elif mode == "letter":
        card = material("Envelope", color=(.57, .43, .34), roughness=.78)
        box("Envelope", (.143, -.125, .001), (.148, .084, .0017), card, angle=-.18, bevel=.0004)

    photo = {
        "lens_mm_equivalent": rng.uniform(23, 31), "roll_deg": rng.uniform(-10, 10),
        "fstop_equivalent": rng.uniform(6.8, 9.5), "k1": rng.uniform(.005, .032),
        "iso": rng.choice((80, 125, 200, 320, 500)), "jpeg_quality": rng.randint(72, 93),
        "shutter_drift_m": rng.choice((0, .00032, .0006, .00085)),
        "exposure_ev": scene.view_settings.exposure,
    }
    if realism:
        effect = realism["camera"]
        photo.update(fstop_equivalent=effect["fstop"] or photo["fstop_equivalent"],
                     defocus_enabled=effect["fstop"] is not None, focus_offset_m=effect["focus_offset_m"],
                     noise_strength=effect["noise_strength"], iso=effect["iso"],
                     shutter_drift_m=effect["motion_m"], motion_angle_deg=effect["motion_angle_deg"],
                     jpeg_quality=94, lighting=scene_lighting["profile"])
    camera = set_camera(scene, rng, mode, photo)
    photo["position_m"] = list(camera.location)
    photo["rotation_wxyz"] = list(camera.rotation_quaternion)
    photo["sensor_width_mm"] = camera.data.sensor_width
    if realism:
        photo["focus_distance_m"] = camera.data.dof.focus_distance
        photo["motion_shutter_frames"] = scene.render.motion_blur_shutter
        for source in scene_lighting["sources"]:
            light(**source)
        if effect["flash_w"]:
            location = camera.location + Vector((effect["flash_x_m"], .016, -.015))
            # Freeze v2 flash aim, including the old paper position used as the target.
            aim_point = sheet.matrix_world @ Vector(reference_paper.at(*effect["flash_uv"]))
            cone = effect["flash_cone_deg"]
            light("Phone flash", "SPOT", location, aim_point, effect["flash_w"], .008, (1, .95, .88), cone)
            photo["flash"] = {"power_w": effect["flash_w"], "position_m": list(location),
                              "target_m": list(aim_point), "cone_degrees": cone}
    else:
        light("Window", "AREA", (-.31, .22, .46), (0, 0, 0), 9.5, .48)
    if not realism and case["seed"] % 5 == 2:
        light("Phone flash", "POINT", camera.location + Vector((.022, -.02, 0)), (0, 0, 0), 1.9, .006)
        photo["lighting"] = "window+flash"
    elif not realism and case["seed"] % 5 == 3:
        dark = material("Shadow occluder", color=(.012, .018, .020))
        box("Off-axis phone shadow", (-.16, .08, .15), (.071, .117, .008), dark, angle=.23)
        photo["lighting"] = "window+phone-shadow"
    elif not realism:
        photo["lighting"] = "window"
    bpy.context.view_layer.update()
    return scene, camera, sheet, paper, photo


def annotations(scene, camera, sheet, paper, case, photo):
    width, height = scene.render.resolution_x, scene.render.resolution_y
    source_width, source_height = case["source_size"]
    camera_pos = camera.matrix_world.translation
    graph = bpy.context.evaluated_depsgraph_get()
    projection = camera.calc_matrix_camera(graph, x=width, y=height).inverted()

    def project(world):
        p = world_to_camera_view(scene, camera, world)
        return p.x * width, (1 - p.y) * height

    def sample(u, v):
        point = sheet.matrix_world @ Vector(paper.at(u, v))
        px, py = project(point)
        radial = distort(px, py, width, height, photo["k1"])
        camera_ray = projection @ Vector((2 * px / width - 1, 1 - 2 * py / height, 1, 1))
        direction = camera.matrix_world.to_3x3() @ (camera_ray.xyz / camera_ray.w).normalized()
        hit, where, _, _, obj, _ = scene.ray_cast(graph, camera_pos, direction)
        inside = 0 <= radial[0] < width and 0 <= radial[1] < height
        on_surface = hit and obj == sheet and (where - point).length < .00055
        error = math.dist((px, py), project(where)) if on_surface else None
        return radial, inside, on_surface, error

    regions = []
    errors = []
    for original in case["annotations"]:
        left, top, right, bottom = [e / d for e, d in zip(original["bbox"], (source_width, source_height) * 2)]
        boundary = [sample(u, v) for u, v in paper.perimeter((left, top, right, bottom))]
        interior = [sample(left + a * (right - left), top + b * (bottom - top))
                    for a in (.08, .29, .5, .71, .92) for b in (.18, .5, .82)]
        checked = boundary + interior
        clipped = sum(not result[1] for result in checked) / len(checked)
        occluded = sum(not result[2] for result in checked) / len(checked)
        errors.extend(result[3] for result in checked if result[3] is not None)
        region = {**original, "polygon": [result[0] for result in boundary],
                  "clipped_sample_fraction": clipped, "occluded_sample_fraction": occluded}
        regions.append(region)
    markers = [sample(*uv)[0] for uv in case.get("marker_uv", [])]
    return regions, errors, markers


def capture(job, case):
    rng = random.Random(case["seed"])
    scene, camera, sheet, paper, photo = scene_for(job, case, rng)
    regions, errors, markers = annotations(scene, camera, sheet, paper, case, photo)
    rejected = [region["id"] for region in regions if max(region["clipped_sample_fraction"],
                region["occluded_sample_fraction"]) > job["max_bad_fraction"]]
    result = {"id": case["id"], "scene": case["scene"], "paper": asdict(paper), "phone": photo,
              "annotations": regions, "rejected_regions": rejected, "marker_positions": markers,
              "inverse_camera_ray_checks": len(errors), "inverse_camera_ray_max_px": max(errors, default=None)}
    if "realism" in case:
        width, height = job["size"]
        camera_matrix = camera.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=width, y=height)
        clip_from_sheet = camera_matrix @ camera.matrix_world.inverted() @ sheet.matrix_world
        if "strong_fold" in case:
            result["strong_fold"] = case["strong_fold"]
        result.update(realism=case["realism"], pair_id=case["pair_id"], arm=case["arm"],
                      clip_from_sheet=[list(row) for row in clip_from_sheet])
    if rejected:
        return result
    start = time.perf_counter()
    scene.render.filepath = case["undistorted"]
    bpy.ops.render.render(write_still=True)
    result["render_seconds"] = time.perf_counter() - start
    if case.get("marker_image"):
        sheet.data.materials[0] = material("Fiducial UV texture", image=case["marker_image"], emission=True)
        camera.data.dof.use_dof = False
        scene.render.use_motion_blur = False
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.exposure = 0
        scene.cycles.device = "CPU"
        scene.cycles.samples = 4
        scene.cycles.use_denoising = False
        scene.render.filepath = case["marker_output"]
        bpy.ops.render.render(write_still=True)
    return result


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
    if bpy.app.version[0] != 5:
        raise RuntimeError("Capture requires Blender 5.x")
    hardware = use_cycles(job["device"])
    started = time.perf_counter()
    rows = [capture(job, case) for case in job["cases"]]
    result = {"blender": bpy.app.version_string, "build_hash": bpy.app.build_hash.decode(),
              "hardware": hardware, "elapsed_seconds": time.perf_counter() - started, "rows": rows}
    Path(job["result"]).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
