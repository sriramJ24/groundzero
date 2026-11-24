"""Simulated vineyard block seen by a tractor-mounted camera, for the demo. Every photo it writes is synthetic.

Builds a 30 x 30 m block of trellised vines (VSP: shoots trained upward between wires), rows 2.5 m apart
running north-south, vines 1.5 m apart, with three problems planted on purpose: yellowing leaves, a thin
canopy, and a missing vine. Vineyards are usually drip-irrigated, so instead of a pivot the same
Camera Module 3 rides on a tractor driving every other alley, one camera looking left and one right, so
every canopy face is photographed once. Writes each photo with the capture-format JSON
(docs/capture-format.md) plus a "simulation" block holding the exact pose, and truth.json listing the
planted problems for honest scoring on simulated data.

  python vineyard_field.py --out out/vineyard --scale 0.25 --samples 16 --only 40   # quick CPU check
  python vineyard_field.py --out out/vineyard --scale 0.5 --samples 32 --gpu        # full pass (GPU)
"""
import argparse, json, math, random, sys, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix

ap = argparse.ArgumentParser()
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--scale", type=float, default=0.25, help="fraction of 4608x2592")
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--every", type=int, default=1)
ap.add_argument("--only", type=str, default="")
ap.add_argument("--gpu", action="store_true")
ap.add_argument("--seed", type=int, default=11)
ap.add_argument("--no-render", action="store_true")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)   # works under `blender -b -P` too
rng = random.Random(a.seed)

SECTION = 30.0
ROW_GAP, VINE_GAP, POST_GAP = 2.5, 1.5, 6.0
NROWS = 12
ROW_X = [-SECTION / 2 + ROW_GAP / 2 + i * ROW_GAP for i in range(NROWS)]
CORDON_Z, CANOPY_TOP = 0.9, 1.9
CAM_H, CAM_TILT, STEP_M = 1.6, 10.0, 1.0
VINE_Y = [-SECTION / 2 + VINE_GAP / 2 + j * VINE_GAP for j in range(int(SECTION / VINE_GAP))]
PROBLEMS = [
    dict(id="V1", kind="yellowing leaves", row=3, vines=[5, 6, 7]),
    dict(id="V2", kind="thin canopy", row=6, vines=[10, 11, 12]),
    dict(id="V3", kind="missing vine", row=9, vines=[14]),
]
for p in PROBLEMS:
    p["x"] = ROW_X[p["row"]]
    p["y"] = [VINE_Y[v] for v in p["vines"]]

def problem_at(ri, vi):
    for p in PROBLEMS:
        if p["row"] == ri and vi in p["vines"]:
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

def principled(name, color, rough=0.6, spec=0.25):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    return m, m.node_tree, b

def leaf_material(name, color, translucent=0.3):
    m, nt, bsdf = principled(name, color, rough=0.5, spec=0.3)
    info = nt.nodes.new("ShaderNodeObjectInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    c = color
    ramp.color_ramp.elements[0].color = (c[0] * 0.75, c[1] * 0.8, c[2] * 0.8, 1)
    ramp.color_ramp.elements[1].color = (min(1, c[0] * 1.2), min(1, c[1] * 1.15), c[2], 1)
    # vary per leaf, using the leaf's position (all leaves of a vine are one object)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "SCALE"; vm.inputs["Scale"].default_value = 9.0
    nt.links.new(geo.outputs["Position"], vm.inputs[0])
    nt.links.new(vm.outputs["Vector"], wn.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
    nt.links.new(info.outputs["Random"], add.inputs[0])
    nt.links.new(wn.outputs["Value"], add.inputs[1])
    half = nt.nodes.new("ShaderNodeMath"); half.operation = "MULTIPLY"; half.inputs[1].default_value = 0.5
    nt.links.new(add.outputs[0], half.inputs[0])
    nt.links.new(half.outputs[0], ramp.inputs["Fac"])
    # veins: radial lines in leaf UV space
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave"); wave.wave_type = "RINGS"
    wave.inputs["Scale"].default_value = 3.0; wave.inputs["Distortion"].default_value = 2.0
    nt.links.new(tc.outputs["UV"], wave.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.12
    nt.links.new(ramp.outputs["Color"], mix.inputs["A"])
    nt.links.new(wave.outputs["Color"], mix.inputs["B"])
    col = mix.outputs["Result"]
    nt.links.new(col, bsdf.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(col, tr.inputs["Color"])
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs["Fac"].default_value = translucent
    out = nt.nodes["Material Output"]
    nt.links.new(bsdf.outputs["BSDF"], mx.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mx.inputs[2])
    nt.links.new(mx.outputs["Shader"], out.inputs["Surface"])
    return m

def noise_material(name, c0, c1, scale=6, bump=0.4):
    m, nt, bsdf = principled(name, c0, rough=0.95, spec=0.1)
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = 12
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c0, 1)
    ramp.color_ramp.elements[1].color = (*c1, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump
    n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = scale * 12
    nt.links.new(n2.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m

M_LEAF = leaf_material("vine_leaf", (0.035, 0.095, 0.018))
M_YELLOW = leaf_material("vine_leaf_yellow", (0.10, 0.10, 0.018))     # chlorosis look
M_WOOD = noise_material("vine_wood", (0.07, 0.045, 0.03), (0.16, 0.11, 0.07), scale=30, bump=0.8)
M_POST = noise_material("post", (0.18, 0.14, 0.10), (0.30, 0.24, 0.17), scale=20)
M_WIRE = principled("wire", (0.5, 0.5, 0.5), rough=0.3, spec=0.6)[0]
M_GRAPE, _, gb = principled("grape", (0.03, 0.02, 0.06), rough=0.25, spec=0.5)
gb.inputs["Coat Weight"].default_value = 0.3
M_SOIL = noise_material("soil", (0.07, 0.05, 0.035), (0.15, 0.11, 0.075))
M_COVER = noise_material("cover_crop", (0.035, 0.05, 0.015), (0.10, 0.09, 0.035), scale=14, bump=1.0)

# ---------------- meshes ----------------
def tube(bm, p0, p1, r0, r1, sides=6):
    axis = (p1 - p0)
    L = axis.length
    q = axis.to_track_quat("Z", "Y")
    M = q.to_matrix()
    ring = lambda p, r: [bm.verts.new(p + M @ Vector((r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides), 0))) for k in range(sides)]
    a0, a1 = ring(p0, r0), ring(p1, r1)
    for k in range(sides):
        bm.faces.new((a0[k], a0[(k + 1) % sides], a1[(k + 1) % sides], a1[k]))

LEAF_UV = {}
def grape_leaf(bm, center, normal, up, size):
    """Five-lobed leaf as a slightly cupped fan, facing `normal`."""
    n = normal.normalized()
    u = (up - n * up.dot(n)).normalized()
    v = n.cross(u)
    pts = []
    N = 24
    for k in range(N):
        th = 2 * math.pi * k / N - math.pi / 2          # start at the petiole (bottom)
        lobes = 0.72 + 0.28 * abs(math.cos(2.5 * (th + math.pi / 2)))
        sinus = 0.55 if abs(th + math.pi / 2) < 0.2 else 1.0
        r = size * 0.5 * lobes * sinus
        x, y = r * math.cos(th), r * math.sin(th) + size * 0.12
        z = -0.18 * size * (x * x + y * y) / (size * size * 0.25)   # cup
        pts.append((x, y, z))
    c = bm.verts.new(center + n * (0.02 * size))
    LEAF_UV[c] = (0.5, 0.5)
    ring = []
    for x, y, z in pts:
        vv = bm.verts.new(center + v * x + u * y + n * z)
        LEAF_UV[vv] = (0.5 + x / size, 0.5 + y / size)
        ring.append(vv)
    for k in range(N):
        bm.faces.new((c, ring[k], ring[(k + 1) % N]))

def vine_mesh(name, seed, leaf_mat, density=1.0):
    r = random.Random(seed)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    tube(bm, Vector((0, 0, 0)), Vector((r.gauss(0, 0.02), 0, CORDON_Z)), 0.045, 0.035)
    for s in (-1, 1):   # bilateral cordon along the fruiting wire
        tube(bm, Vector((0, 0, CORDON_Z - 0.02)), Vector((0, s * VINE_GAP * 0.5, CORDON_Z + 0.01)), 0.03, 0.018)
    wood_faces = len(bm.faces)
    shoots = 20
    for i in range(shoots):
        y0 = (i + 0.5) / shoots * VINE_GAP - VINE_GAP / 2 + r.gauss(0, 0.03)
        base = Vector((r.gauss(0, 0.03), y0, CORDON_Z + 0.03))
        top = Vector((r.gauss(0, 0.08), y0 + r.gauss(0, 0.08), CANOPY_TOP + r.gauss(0, 0.08)))
        nleaf = int(14 * density + r.random())
        for k in range(nleaf):
            t = (k + 0.7) / (nleaf + 0.5) if density >= 1 else (k + 0.7) / (14 + 0.5)
            p = base.lerp(top, t)
            side = 1 if (k + i) % 2 else -1
            # leaves hang off the shoot, facing out of the row with some tilt
            nrm = Vector((side, r.gauss(0, 0.5), r.uniform(0.0, 0.8)))
            off = Vector((side * r.uniform(0.06, 0.2), r.gauss(0, 0.05), r.gauss(0, 0.03)))
            grape_leaf(bm, p + off, nrm, Vector((0, 0, 1)) + Vector((r.gauss(0, 0.4), r.gauss(0, 0.4), 0)), r.uniform(0.11, 0.17))
        # a few lateral leaves fill the canopy
        for k in range(int(8 * density)):
            p = base.lerp(top, r.uniform(0.3, 0.95)) + Vector((r.gauss(0, 0.12), r.gauss(0, 0.1), 0))
            grape_leaf(bm, p, Vector((r.choice((-1, 1)), r.gauss(0, 0.6), r.uniform(-0.2, 0.8))), Vector((0, 0, 1)), r.uniform(0.07, 0.11))
    leaf_end = len(bm.faces)
    for i in range(6):   # clusters below the canopy
        cy = r.uniform(-0.6, 0.6)
        cx = r.choice((-1, 1)) * r.uniform(0.04, 0.1)
        for b in range(34):
            t = r.random()
            z = CORDON_Z - 0.03 - t * 0.16
            rad = 0.045 * (1 - 0.7 * t)
            ang = r.uniform(0, 6.28)
            c = Vector((cx + rad * math.cos(ang), cy + rad * math.sin(ang), z))
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.009, matrix=Matrix.Translation(c))
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = LEAF_UV.get(loop.vert, (0.5, 0.5))
    bm.to_mesh(me)
    for m in (M_WOOD, leaf_mat, M_GRAPE):
        me.materials.append(m)
    for i, poly in enumerate(me.polygons):
        poly.material_index = 0 if i < wood_faces else (1 if i < leaf_end else 2)
        poly.use_smooth = True
    return me

VAR = 6
normal = [vine_mesh(f"vine_{i}", a.seed * 100 + i, M_LEAF) for i in range(VAR)]
yellow = [vine_mesh(f"vine_y_{i}", a.seed * 100 + i, M_YELLOW) for i in range(VAR)]
thin = [vine_mesh(f"vine_t_{i}", a.seed * 100 + i, M_LEAF, density=0.4) for i in range(VAR)]

# ---------------- block ----------------
def plane(name, x0, x1, y0, y1, z, mat, segs=1):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    bm.faces.new(vs)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    scene.collection.objects.link(ob)

EXT = SECTION / 2 + 15
plane("soil", -EXT, EXT, -EXT, EXT, 0, M_SOIL)
rows_all = [x for x in [ROW_X[0] - ROW_GAP * k for k in range(1, 5)][::-1] + ROW_X + [ROW_X[-1] + ROW_GAP * k for k in range(1, 5)]]
for x in rows_all[:-1]:       # cover crop in each alley, bare strip under the vines
    plane("cover", x + 0.45, x + ROW_GAP - 0.45, -EXT, EXT, 0.01, M_COVER)

col = bpy.data.collections.new("vines")
scene.collection.children.link(col)
counts = dict(vines=0, yellowing=0, thin=0, missing=0)
wire_z = (CORDON_Z, 1.25, 1.6, CANOPY_TOP - 0.05)
for ri, x in enumerate(rows_all):
    inside = x in ROW_X
    rii = ROW_X.index(x) if inside else -1
    ys = VINE_Y if inside else [y for y in VINE_Y]
    ylo, yhi = -EXT + 2, EXT - 2
    # posts and wires along the whole row
    y = ylo
    while y <= yhi:
        me = bpy.data.meshes.new("post"); bm = bmesh.new()
        tube(bm, Vector((0, 0, 0)), Vector((0, 0, CANOPY_TOP + 0.1)), 0.05, 0.05, sides=8); bm.to_mesh(me)
        ob = bpy.data.objects.new("post", me); ob.data.materials.append(M_POST); ob.location = (x, y, 0); col.objects.link(ob)
        y += POST_GAP
    for z in wire_z:
        for dx in ((0,) if z == CORDON_Z else (-0.12, 0.12)):
            me = bpy.data.meshes.new("wire"); bm = bmesh.new()
            tube(bm, Vector((x + dx, ylo, z)), Vector((x + dx, yhi, z)), 0.0016, 0.0016, sides=4); bm.to_mesh(me)
            ob = bpy.data.objects.new("wire", me); ob.data.materials.append(M_WIRE); col.objects.link(ob)
    # vines, extended past the section so edge photos still show a full row
    yy = VINE_Y[0] - VINE_GAP * math.ceil((VINE_Y[0] - ylo) / VINE_GAP)
    vi_all = 0
    while yy < yhi:
        k = round((yy - VINE_Y[0]) / VINE_GAP)
        vi = k if (inside and 0 <= k < len(VINE_Y) and abs(VINE_Y[k] - yy) < 0.01) else -1
        p = problem_at(rii, vi) if inside and vi >= 0 else None
        if p and p["kind"] == "missing vine":
            counts["missing"] += 1
        else:
            pool = yellow if (p and p["kind"] == "yellowing leaves") else thin if (p and p["kind"] == "thin canopy") else normal
            ob = bpy.data.objects.new("vine", pool[rng.randrange(VAR)])
            ob.location = (x + rng.gauss(0, 0.01), yy + rng.gauss(0, 0.03), 0)
            ob.rotation_euler = (0, 0, math.pi * rng.randrange(2) + rng.gauss(0, 0.03))
            col.objects.link(ob)
            if inside and vi >= 0:
                counts["vines"] += 1
                if p:
                    counts["yellowing" if p["kind"] == "yellowing leaves" else "thin"] += 1
        yy = round(yy + VINE_GAP, 4)

# ---------------- light ----------------
world = bpy.data.worlds.new("sky"); scene.world = world; world.use_nodes = True
sky = world.node_tree.nodes.new("ShaderNodeTexSky")
try:
    sky.sky_type = "NISHITA"
except TypeError:
    pass
sky.sun_elevation = math.radians(42); sky.sun_rotation = math.radians(160)
world.node_tree.links.new(sky.outputs["Color"], world.node_tree.nodes["Background"].inputs["Color"])
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.22
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.0; sun.data.angle = math.radians(1.0)
sun.rotation_euler = (math.radians(48), 0, math.radians(160))
scene.collection.objects.link(sun)

# ---------------- tractor camera path ----------------
cam_data = bpy.data.cameras.new("tractorcam")
cam_data.lens = 4.74; cam_data.sensor_fit = "HORIZONTAL"; cam_data.sensor_width = 6.45
cam = bpy.data.objects.new("tractorcam", cam_data)
scene.collection.objects.link(cam); scene.camera = cam

ALLEYS = [ROW_X[i] + ROW_GAP / 2 for i in range(0, NROWS, 2)]   # every other alley: rows i and i+1
shots = []
for ai, ax in enumerate(ALLEYS):
    ys = [-SECTION / 2 - 1 + k * STEP_M for k in range(int((SECTION + 2) / STEP_M) + 1)]
    if ai % 2:
        ys = ys[::-1]          # the tractor turns at the headland and comes back
    for y in ys:
        for side, sname in ((-1, "L"), (1, "R")):
            heading_dir = 1 if ai % 2 == 0 else -1     # +1 = driving north
            look = Vector((side, 0, 0))
            shots.append(dict(alley=ai, side=sname, pos=Vector((ax, y, CAM_H)), look=look, drive=heading_dir,
                              row=(ROW_X.index(ax - ROW_GAP / 2) if side < 0 else ROW_X.index(ax + ROW_GAP / 2))))

start = datetime(2026, 8, 20, 16, 0, 0, tzinfo=timezone.utc)
SPEED = 1.5   # m/s
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "photos").mkdir(exist_ok=True)
boot = str(uuid.UUID(int=a.seed))
only = {int(s) for s in a.only.split(",") if s.strip()}
seqs = {"L": 0, "R": 0}
for i, s in enumerate(shots):
    seqs[s["side"]] += 1
    seconds = (i // 2) * STEP_M / SPEED + s["alley"] * 40
    t = start + timedelta(seconds=seconds)
    device = f"sim-tractorcam-{s['side']}"
    cid = t.strftime("%Y%m%dT%H%M%S") + f"{t.microsecond // 1000:03d}Z_{seqs[s['side']]:06d}"
    yaw = math.atan2(s["look"].y, s["look"].x)
    rot = (math.radians(90 - CAM_TILT), 0, yaw - math.pi / 2)
    heading = (90 - math.degrees(yaw)) % 360
    meta = {
        "format_version": "0.1-draft", "capture_id": cid, "device_id": device, "field_id": "sim-vineyard-block",
        "synthetic": True,
        "time": {"utc": t.isoformat(timespec="milliseconds").replace("+00:00", "Z"), "source": "unsynced",
                 "boot_id": boot, "monotonic_ms": int(seconds * 1000)},
        "camera": {"tilt_deg": CAM_TILT, "tilt_source": "installed", "roll_deg": 0.0, "heading_deg": round(heading, 3),
                   "height_m": CAM_H, "model": "camera-module-3", "lens": "standard",
                   "resolution": [scene.render.resolution_x, scene.render.resolution_y]},
        "gps": None,
        "simulation": {"note": "Rendered in Blender, not a camera photo. Pose is exact.", "mount": "tractor",
                       "position_m": [round(v, 4) for v in s["pos"]], "rotation_euler_xyz_rad": [round(v, 6) for v in rot],
                       "frame": "block: x east, y north, z up from ground, origin at block centre",
                       "lens_mm": 4.74, "sensor_width_mm": 6.45, "alley": s["alley"], "facing_row": s["row"],
                       "pass_id": "sim-pass-001"},
    }
    (a.out / "photos" / device).mkdir(exist_ok=True)
    (a.out / "photos" / device / f"{cid}.json").write_text(json.dumps(meta, indent=2))
    if a.no_render or (only and i not in only) or (not only and i % a.every):
        continue
    cam.location = s["pos"]; cam.rotation_euler = rot
    scene.render.filepath = str((a.out / "photos" / device / f"{cid}.jpg").resolve())
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"rendered {i + 1}/{len(shots)} {device}/{cid} in {time.time() - t0:.1f} s", flush=True)

truth = dict(note="Planted problems in the simulated vineyard block. Use only to score flags on simulated data.",
             frame="block: x east, y north (m), origin at block centre", section_m=SECTION, row_gap_m=ROW_GAP,
             vine_gap_m=VINE_GAP, row_x_m=ROW_X, vine_y_m=VINE_Y, canopy_m=[CORDON_Z, CANOPY_TOP], problems=PROBLEMS,
             vines=counts, cameras=dict(mount="tractor", height_m=CAM_H, tilt_deg=CAM_TILT, step_m=STEP_M, alleys_x_m=ALLEYS),
             photos=len(shots))
(a.out / "truth.json").write_text(json.dumps(truth, indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str((a.out / "vineyard_block.blend").resolve()))
print(json.dumps(dict(photos=len(shots), **counts)))
