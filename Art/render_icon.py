# Renders the build-menu icons in the vanilla style: the model itself, 3/4 view from slightly
# above, soft studio light, TRANSPARENT background, cropped tight to the model.
#
#   blender -b --factory-startup --python Art/render_icon.py
#
# Builds the scene by running Art/build_mesh.py with its FBX export skipped (so this never
# touches Art/Export), then writes Art/Icon_AdvancedFluidBuffer_512.png, _256.png and the mod
# logo Resources/Icon128.png.
# Re-run after any model change, then re-run Scripts/regenerate_assets.ps1 to import them.
import math
import os

import bpy
import numpy as np
from mathutils import Vector

ART = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(ART, "build_mesh.py")
RENDER_SIZE = 1024
SIZES = (512, 256)
MARGIN = 0.04            # empty border around the model, fraction of the icon size
CAMERA_AZIMUTH = -28.0   # degrees from +X (Blender); shows the 75% port and the sight strip
CAMERA_ELEVATION = 22.0  # degrees above horizontal
CAMERA_LENS = 70.0       # mm; mild perspective like the vanilla icons
FILL_FRACTION = 0.6      # visual tank fill in the icon

# 1. Build the model without exporting.
src = open(MODEL, encoding="utf-8").read()
marker = "\nexport_all_fbx()"
assert src.count(marker) == 1, "build_mesh.py entry point changed; update render_icon.py"
g = {"__name__": "__main__", "__file__": MODEL}
exec(compile(src.replace(marker, "\n# export skipped by render_icon.py"), MODEL, "exec"), g)

scene = bpy.context.scene
main, liquid, glass = g["main"], g["liquid"], g["glass"]
show = {main, liquid, glass}
for obj in scene.objects:
    visible = obj in show
    obj.hide_render = not visible
    obj.hide_set(not visible)
liquid.scale.z = FILL_FRACTION

# 2. Render settings: Cycles, transparent film, neutral colour so the paint reads like in game.
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = RENDER_SIZE
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.view_settings.exposure = 0.0

world = bpy.data.worlds.get("IconWorld") or bpy.data.worlds.new("IconWorld")
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.55, 0.58, 0.62, 1.0)   # soft ambient fill
bg.inputs["Strength"].default_value = 0.9
scene.world = world

# 3. Model bounds (world space) for aiming the camera and placing lights.
pts = [main.matrix_world @ Vector(c) for c in main.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre = (lo + hi) / 2
radius = (hi - lo).length / 2


def direction(azimuth, elevation):
    a, e = math.radians(azimuth), math.radians(elevation)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def add_light(name, kind, energy, azimuth, elevation, distance, size):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    if kind == "AREA":
        data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = centre + direction(azimuth, elevation) * distance
    obj.rotation_euler = (centre - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


# Key from front-left above, fill from the right, rim from behind for the silhouette edge.
d = radius * 3.0
add_light("Key", "AREA", 6.0e7, CAMERA_AZIMUTH + 40, 45, d, radius * 1.5)
add_light("Fill", "AREA", 2.5e7, CAMERA_AZIMUTH - 70, 15, d, radius * 2.0)
add_light("Rim", "AREA", 3.0e7, CAMERA_AZIMUTH + 170, 35, d, radius * 1.5)

# 4. Camera far enough back to frame the whole model; the PNG is cropped afterwards anyway.
cam_data = bpy.data.cameras.new("IconCamera")
cam_data.lens = CAMERA_LENS
cam_data.clip_end = 1.0e6
cam = bpy.data.objects.new("IconCamera", cam_data)
scene.collection.objects.link(cam)
half_fov = math.atan(cam_data.sensor_width / 2 / CAMERA_LENS)
cam.location = centre + direction(CAMERA_AZIMUTH, CAMERA_ELEVATION) * (radius / math.sin(half_fov) * 1.05)
cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

raw = os.path.join(bpy.app.tempdir or ART, "afb_icon_raw.png")
scene.render.filepath = raw
bpy.ops.render.render(write_still=True)

# 5. Crop to the alpha bounding box, pad to a square with a margin, scale and save.
img = bpy.data.images.load(raw)
w, h = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
ys, xs = np.nonzero(px[:, :, 3] > 0.01)
assert len(xs), "icon render is empty"
x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
crop = px[y0:y1, x0:x1]
side = int(max(crop.shape[0], crop.shape[1]) / (1 - 2 * MARGIN))
canvas = np.zeros((side, side, 4), dtype=np.float32)
oy, ox = (side - crop.shape[0]) // 2, (side - crop.shape[1]) // 2
canvas[oy:oy + crop.shape[0], ox:ox + crop.shape[1]] = crop

# Build-menu icons, plus the mod logo (Resources/Icon128.png, shown by mod managers).
targets = [(s, os.path.join(ART, f"Icon_AdvancedFluidBuffer_{s}.png")) for s in SIZES]
targets.append((128, os.path.join(os.path.dirname(ART), "Resources", "Icon128.png")))
for size, path in targets:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = bpy.data.images.new(f"icon_{size}", side, side, alpha=True)
    out.pixels.foreach_set(canvas.ravel())
    out.scale(size, size)
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    print(f"ICON: wrote {path}")
