"""Simulated corn section seen by PivotCam, for the demo. Every photo it writes is synthetic.

Builds a 30 x 30 m block of corn (rows 0.76 m apart) with three problem patches planted on purpose
(short plants, pale plants, a gap), then renders the photos three Pi cameras on the pivot span would take
during one pass. Writes each photo with the capture-format JSON (docs/capture-format.md) plus a
"simulation" block holding the exact camera pose, and truth.json listing where the problems are, so the
flags can be scored honestly ("found N of M planted problems, on simulated data").

Run with Blender's Python module (pip install bpy==5.3.0 numpy):
  python corn_field.py --out out/corn --scale 0.25 --samples 16 --every 10   # quick CPU check
  python corn_field.py --out out/corn --scale 1 --samples 64 --gpu             # full pass (handoff to GPU)
"""
import argparse, json, math, random, sys, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--scale", type=float, default=0.25, help="fraction of 4608x2592")
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--every", type=int, default=1, help="render every Nth photo (for quick checks)")
ap.add_argument("--only", type=str, default="", help="comma list of photo indexes to render")
ap.add_argument("--gpu", action="store_true")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--no-render", action="store_true", help="write metadata and the .blend only")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)   # works under `blender -b -P` too
rng = random.Random(a.seed)

# ---------------- field layout (metres; section centred on origin, x east, y north, z up) ----------------
SECTION = 30.0
ROW_GAP, PLANT_GAP = 0.76, 0.20
PLANT_H = 1.7                      # around V12, before tassel
PIVOT_CENTER = Vector((-160.0, 0.0, 0.0))   # section sits 145-175 m out along the span
CAM_RADII = [146.0, 156.0, 166.0]           # three Pi units on the span, ~10 m apart
CAM_H, CAM_TILT = 4.0, 35.0                 # metres above ground on the pipe, degrees down
STEP_M = 0.5                                # photo every 0.5 m of travel at the camera
PROBLEMS = [
    dict(id="P1", kind="short plants", x=-6.0, y=6.0, r=2.2, height=0.55),
    dict(id="P2", kind="pale plants", x=5.0, y=-7.0, r=2.5),
    dict(id="P3", kind="missing plants", x=8.0, y=8.0, length=3.5),
]

def in_problem(x, y):
    for p in PROBLEMS:
        if p["kind"] == "missing plants":
            if abs(y - p["y"]) < ROW_GAP * 1.5 and abs(x - p["x"]) < p["length"] / 2:
                return p
        elif (x - p["x"]) ** 2 + (y - p["y"]) ** 2 < p["r"] ** 2:
            return p
    return None

# ---------------- scene ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True
if a.gpu:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type != "CPU"
            break
        except Exception:
            continue
    scene.cycles.device = "GPU"
scene.render.resolution_x = int(4608 * a.scale)
scene.render.resolution_y = int(2592 * a.scale)
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 92
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"

def material(name, color, rough=0.6, sss=0.0, noise_mix=0.15, translucent=0.25):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = 0.22
    # per-object colour jitter so neighbouring plants differ a little
    info = nt.nodes.new("ShaderNodeObjectInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    c = color
    ramp.color_ramp.elements[0].color = (c[0] * 0.8, c[1] * 0.85, c[2] * 0.8, 1)
    ramp.color_ramp.elements[1].color = (min(1, c[0] * 1.15), min(1, c[1] * 1.1), c[2], 1)
    nt.links.new(info.outputs["Random"], ramp.inputs["Fac"])
    # leaf veins / mottling
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 40
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = noise_mix
    nt.links.new(ramp.outputs["Color"], mix.inputs["A"])
    nt.links.new(tex.outputs["Color"], mix.inputs["B"])
    leaf_col = mix.outputs["Result"]
    # pale midrib down the centre of each leaf (u = 0.5)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs["Vector"])
    dist = nt.nodes.new("ShaderNodeMath"); dist.operation = "SUBTRACT"; dist.inputs[1].default_value = 0.5
    nt.links.new(sep.outputs["X"], dist.inputs[0])
    ab = nt.nodes.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"
    nt.links.new(dist.outputs[0], ab.inputs[0])
    rib = nt.nodes.new("ShaderNodeMapRange")
    rib.inputs["From Min"].default_value = 0.0; rib.inputs["From Max"].default_value = 0.06
    rib.inputs["To Min"].default_value = 0.55; rib.inputs["To Max"].default_value = 0.0
    nt.links.new(ab.outputs[0], rib.inputs["Value"])
    m2 = nt.nodes.new("ShaderNodeMix"); m2.data_type = "RGBA"; m2.blend_type = "SCREEN"
    m2.inputs["B"].default_value = (0.25, 0.32, 0.12, 1)
    nt.links.new(rib.outputs["Result"], m2.inputs["Factor"])
    nt.links.new(leaf_col, m2.inputs["A"])
    leaf_col = m2.outputs["Result"]
    nt.links.new(leaf_col, bsdf.inputs["Base Color"])
    if translucent > 0:
        tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
        nt.links.new(leaf_col, tr.inputs["Color"])
        mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = translucent
        out = nt.nodes["Material Output"]
        nt.links.new(bsdf.outputs["BSDF"], mx.inputs[1])
        nt.links.new(tr.outputs["BSDF"], mx.inputs[2])
        nt.links.new(mx.outputs["Shader"], out.inputs["Surface"])
    return m

M_LEAF = material("leaf", (0.035, 0.12, 0.018))
M_PALE = material("leaf_pale", (0.16, 0.20, 0.03))        # nitrogen-short look: yellow-green
M_STALK = material("stalk", (0.06, 0.12, 0.025), translucent=0)

def soil():
    m = bpy.data.materials.new("soil")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.95
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 6
    n.inputs["Detail"].default_value = 12
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.09, 0.065, 0.045, 1)
    ramp.color_ramp.elements[1].color = (0.20, 0.15, 0.10, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 60
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def add_ground():
    half = SECTION / 2 + 25
    me = bpy.data.meshes.new("ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=200, y_segments=200, size=half)
    for v in bm.verts:   # gentle micro-relief, plus furrows along the rows
        v.co.z = 0.03 * math.sin(v.co.x * 0.7) * math.cos(v.co.y * 0.5) + 0.015 * math.cos(2 * math.pi * v.co.x / ROW_GAP)
    bm.to_mesh(me)
    ob = bpy.data.objects.new("ground", me)
    ob.data.materials.append(soil())
    scene.collection.objects.link(ob)

# ---------------- plant meshes ----------------
UV = {}   # vertex -> (u across the leaf, v along it); applied when the mesh is finished

def leaf_strip(bm, base, yaw, length, width, rise, droop, twist, fold=0.25, wave=0.012):
    """A corn leaf: a ribbon folded along its midrib (a shallow V), leaving the stalk upward, arching out
    and drooping at the tip, with a slightly wavy edge."""
    n = 14
    prev = None
    d = Vector((math.cos(yaw), math.sin(yaw), 0))
    side = Vector((-d.y, d.x, 0))
    ph = random.random() * 6.28
    for i in range(n + 1):
        t = i / n
        out = length * t
        up = rise * math.sin(math.pi * 0.5 * min(1, t * 1.8)) - droop * t ** 2.0
        c = base + d * out + Vector((0, 0, up))
        w = width * (0.35 + 0.65 * math.sin(math.pi * min(1.0, 0.15 + 0.95 * t))) * (1 - 0.85 * t ** 3)
        s = side * w / 2
        tw = Vector((0, 0, twist * t * w))
        crease = Vector((0, 0, fold * w * (1 - t)))        # midrib sits higher than the edges
        wv = Vector((0, 0, wave * math.sin(ph + t * 40) * min(1, t * 4)))
        row = (bm.verts.new(c - s - tw + wv), bm.verts.new(c + crease), bm.verts.new(c + s + tw - wv))
        for k, v in enumerate(row):
            UV[v] = (k / 2, t)
        if prev:
            bm.faces.new((prev[0], prev[1], row[1], row[0]))
            bm.faces.new((prev[1], prev[2], row[2], row[1]))
        prev = row

def plant_mesh(name, h, leaf_mat, seed):
    r = random.Random(seed)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    # stalk: tapered 6-sided tube
    ring = 6
    rings = []
    for k in range(6):
        z = h * 0.82 * k / 5
        rad = 0.014 * (1 - 0.55 * k / 5)
        rings.append([bm.verts.new((rad * math.cos(2 * math.pi * j / ring), rad * math.sin(2 * math.pi * j / ring), z)) for j in range(ring)])
    for k in range(5):
        for j in range(ring):
            bm.faces.new((rings[k][j], rings[k][(j + 1) % ring], rings[k + 1][(j + 1) % ring], rings[k + 1][j]))
    stalk_faces = len(bm.faces)
    # leaves: alternate sides (corn leaves sit in one plane, roughly across the row), ~13 leaves
    yaw0 = r.uniform(-0.4, 0.4) + math.pi / 2
    nleaf = 13
    for i in range(nleaf):
        t = (i + 1) / (nleaf + 1)
        z = h * (0.08 + 0.78 * t)
        yaw = yaw0 + (math.pi if i % 2 else 0) + r.uniform(-0.5, 0.5)
        mid = 1 - abs(t - 0.45) * 1.3
        length = h * (0.30 + 0.28 * mid) * r.uniform(0.85, 1.1)
        leaf_strip(bm, Vector((0, 0, z)), yaw, length * 1.25, 0.10 * (0.65 + 0.35 * mid),
                   rise=length * (0.42 - 0.25 * t), droop=length * r.uniform(0.6, 1.0), twist=r.uniform(-0.3, 0.3))
    # the whorl: two young leaves still rolled up at the top
    for i in range(2):
        leaf_strip(bm, Vector((0, 0, h * 0.84)), yaw0 + i * math.pi + r.uniform(-0.3, 0.3), h * 0.22, 0.045,
                   rise=h * 0.2, droop=0.05, twist=0.1, fold=0.6)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = UV.get(loop.vert, (0.5, 0.5))
    bm.to_mesh(me)
    me.materials.append(M_STALK)
    me.materials.append(leaf_mat)
    for i, poly in enumerate(me.polygons):
        poly.material_index = 0 if i < stalk_faces else 1
        poly.use_smooth = True
    return me

VARIANTS = 8
normal = [plant_mesh(f"corn_{i}", PLANT_H, M_LEAF, a.seed * 100 + i) for i in range(VARIANTS)]
pale = [plant_mesh(f"corn_pale_{i}", PLANT_H * 0.92, M_PALE, a.seed * 100 + i) for i in range(VARIANTS)]

# ---------------- place plants ----------------
add_ground()
col = bpy.data.collections.new("corn")
scene.collection.children.link(col)
half = SECTION / 2 + 8          # a margin beyond the section so edge photos still show crop
count = dict(planted=0, short=0, pale=0, missing=0)
nrows = int(2 * half / ROW_GAP)
for ri in range(nrows):
    x = -half + ri * ROW_GAP     # rows run north-south (along y)
    y = -half + rng.uniform(0, PLANT_GAP)
    while y < half:
        px, py = x + rng.gauss(0, 0.02), y + rng.gauss(0, 0.03)
        y += PLANT_GAP * rng.uniform(0.75, 1.25)
        if rng.random() < 0.02:        # normal ~2 % stand loss everywhere
            continue
        p = in_problem(px, py)
        if p and p["kind"] == "missing plants":
            count["missing"] += 1
            continue
        meshes = pale if (p and p["kind"] == "pale plants") else normal
        ob = bpy.data.objects.new("c", meshes[rng.randrange(VARIANTS)])
        ob.location = (px, py, 0)
        ob.rotation_euler = (rng.gauss(0, 0.04), rng.gauss(0, 0.04), rng.uniform(-0.35, 0.35))
        s = rng.gauss(1.0, 0.06)
        if p and p["kind"] == "short plants":
            d = math.hypot(px - p["x"], py - p["y"]) / p["r"]
            s *= p["height"] + (1 - p["height"]) * d ** 2      # shortest in the middle
            count["short"] += 1
        if p and p["kind"] == "pale plants":
            count["pale"] += 1
        ob.scale = (s ** 0.5, s ** 0.5, s)
        col.objects.link(ob)
        count["planted"] += 1

# ---------------- light ----------------
world = bpy.data.worlds.new("sky")
scene.world = world
world.use_nodes = True
sky = world.node_tree.nodes.new("ShaderNodeTexSky")
try:
    sky.sky_type = "NISHITA"
except TypeError:
    pass
sky.sun_elevation = math.radians(38)
sky.sun_rotation = math.radians(200)
world.node_tree.links.new(sky.outputs["Color"], world.node_tree.nodes["Background"].inputs["Color"])
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 4.0
sun.data.angle = math.radians(1.0)
sun.rotation_euler = (math.radians(52), 0, math.radians(200))
scene.collection.objects.link(sun)

# ---------------- PivotCam path ----------------
# Camera Module 3 (standard lens): 4.74 mm focal length on a 6.45 mm-wide sensor, ~66-68 deg wide.
cam_data = bpy.data.cameras.new("pivotcam")
cam_data.lens = 4.74
cam_data.sensor_fit = "HORIZONTAL"
cam_data.sensor_width = 6.45
cam = bpy.data.objects.new("pivotcam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

shots = []
for ci, R in enumerate(CAM_RADII):
    # angular range that keeps this camera's view over the section (plus a little)
    span = math.degrees((SECTION / 2 + 4) / R)
    dtheta = math.degrees(STEP_M / R)
    k = 0
    th = -span
    while th <= span:
        t = math.radians(th)
        pos = PIVOT_CENTER + Vector((R * math.cos(t), R * math.sin(t), CAM_H))
        out = Vector((math.cos(t), math.sin(t), 0))          # looks outward along the span
        shots.append(dict(cam=ci, radius=R, theta=th, pos=pos, out=out))
        th += dtheta
        k += 1

start = datetime(2026, 7, 15, 15, 0, 0, tzinfo=timezone.utc)
ARM_SPEED = 2.4 / 60      # m/s at the outer camera, typical end-tower pace
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "photos").mkdir(exist_ok=True)
boot = str(uuid.UUID(int=a.seed))
only = {int(s) for s in a.only.split(",") if s.strip()}
manifest = []
for i, s in enumerate(shots):
    device = f"sim-pivotcam-{s['cam'] + 1}"
    seconds = (s["theta"] + 30) * math.radians(1) * CAM_RADII[-1] / ARM_SPEED
    t = start + timedelta(seconds=seconds)
    seq = i + 1
    cid = t.strftime("%Y%m%dT%H%M%S") + f"{t.microsecond // 1000:03d}Z_{seq:06d}"
    yaw = math.atan2(s["out"].y, s["out"].x)
    rot = (math.radians(90 - CAM_TILT), 0, yaw - math.pi / 2)
    heading = (90 - math.degrees(yaw)) % 360
    meta = {
        "format_version": "0.1-draft",
        "capture_id": cid,
        "device_id": device,
        "field_id": "sim-corn-section",
        "synthetic": True,
        "time": {"utc": t.isoformat(timespec="milliseconds").replace("+00:00", "Z"), "source": "unsynced",
                 "boot_id": boot, "monotonic_ms": int(seconds * 1000)},
        "camera": {"tilt_deg": CAM_TILT, "tilt_source": "installed", "roll_deg": 0.0, "heading_deg": round(heading, 3),
                   "height_m": CAM_H, "model": "camera-module-3", "lens": "standard",
                   "resolution": [scene.render.resolution_x, scene.render.resolution_y]},
        "pivot": {"angle_deg": None, "angle_source": "none", "camera_radius_m": s["radius"], "pass_id": "sim-pass-001"},
        "gps": None,
        "simulation": {"note": "Rendered in Blender, not a camera photo. Pose is exact.",
                       "position_m": [round(v, 4) for v in s["pos"]], "rotation_euler_xyz_rad": [round(v, 6) for v in rot],
                       "frame": "section: x east, y north, z up from ground, origin at section centre",
                       "lens_mm": 4.74, "sensor_width_mm": 6.45, "pivot_theta_deg": round(s["theta"], 4)},
    }
    manifest.append(meta)
    (a.out / "photos" / device).mkdir(exist_ok=True)
    (a.out / "photos" / device / f"{cid}.json").write_text(json.dumps(meta, indent=2))
    if a.no_render or (only and i not in only) or (not only and i % a.every):
        continue
    cam.location = s["pos"]
    cam.rotation_euler = rot
    scene.render.filepath = str((a.out / "photos" / device / f"{cid}.jpg").resolve())
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"rendered {i + 1}/{len(shots)} {device}/{cid} in {time.time() - t0:.1f} s", flush=True)

truth = dict(note="Planted problems in the simulated section. Use only to score flags on simulated data.",
             frame="section: x east, y north (m), origin at section centre", section_m=SECTION,
             row_gap_m=ROW_GAP, plant_height_m=PLANT_H, problems=PROBLEMS, plants=count,
             cameras=dict(radii_m=CAM_RADII, height_m=CAM_H, tilt_deg=CAM_TILT, step_m=STEP_M,
                          pivot_center_m=list(PIVOT_CENTER)), photos=len(shots))
(a.out / "truth.json").write_text(json.dumps(truth, indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str((a.out / "corn_section.blend").resolve()))
print(json.dumps(dict(photos=len(shots), **count)))
