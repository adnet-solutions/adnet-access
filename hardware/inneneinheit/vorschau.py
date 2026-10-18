"""Vorschaubilder der Inneneinheit -> images/inneneinheit.png, images/inneneinheit_leer.png

    python3 hardware/inneneinheit/generate_innen.py
    python3 hardware/inneneinheit/vorschau.py        (benoetigt: pip install embreex)
"""
import json
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, JoinType
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
STL, IMG = BASE / "stl", BASE / "images"


def load(p):
    return trimesh.load(p)


def rbox(w, h, d, r, x, y, z0):
    cs = CrossSection.square((w - 2 * r, h - 2 * r), center=True).offset(r, JoinType.Round, circular_segments=48)
    m = cs.extrude(d).translate((x, y, z0)).to_mesh()
    return trimesh.Trimesh(m.vert_properties[:, :3], m.tri_verts)


COLORS = {
    "wall": ([0.86, 0.84, 0.80], 0.0), "plate": ([0.20, 0.21, 0.23], 0.15),
    "insert": ([0.24, 0.25, 0.27], 0.15), "text": ([0.95, 0.95, 0.93], 0.1),
    "glow": ([0.35, 1.0, 0.45], 0.0), "bell": ([0.70, 0.71, 0.72], 0.5),
    "rfid": ([0.25, 0.45, 0.80], 0.3), "led": ([0.55, 0.57, 0.60], 0.3), "tag": ([0.85, 0.75, 0.30], 0.2),
    "box": ([0.93, 0.93, 0.92], 0.1), "atom": ([0.15, 0.15, 0.16], 0.3),
    "buck": ([0.72, 0.74, 0.76], 0.5), "wago": ([0.85, 0.55, 0.20], 0.2),
    "delock": ([0.15, 0.15, 0.16], 0.2), "bar": ([0.97, 0.97, 0.96], 0.1),
}


def render(parts, cam, target, out, size=(1400, 900), fov=40, light=(-0.45, 0.75, 0.6), emissive=("glow",)):
    meshes, ids = [], []
    for k, lst in parts.items():
        for m in lst:
            meshes.append(m)
            ids += [k] * len(m.faces)
    scene = trimesh.util.concatenate(meshes)
    ids = np.array(ids)
    inter = trimesh.ray.ray_pyembree.RayMeshIntersector(scene)
    W, H = size
    cam, target = np.array(cam, float), np.array(target, float)
    fwd = target - cam; fwd /= np.linalg.norm(fwd)
    upv = np.array([0, 1, 0]) if abs(fwd[1]) < 0.95 else np.array([0, 0, 1])
    right = np.cross(fwd, upv); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    px, py = np.meshgrid(np.linspace(-1, 1, W), np.linspace(-1, 1, H) * H / W)
    dirs = fwd + np.tan(np.radians(fov) / 2) * (px[..., None] * right + -py[..., None] * up)
    dirs = (dirs / np.linalg.norm(dirs, axis=-1, keepdims=True)).reshape(-1, 3)
    orig = np.tile(cam, (len(dirs), 1))
    tri, ray, loc = inter.intersects_id(orig, dirs, multiple_hits=False, return_locations=True)
    img = np.ones((W * H, 3)) * np.array([0.95, 0.95, 0.94])
    n = scene.face_normals[tri]
    n[(n * dirs[ray]).sum(1) > 0] *= -1
    L = np.array(light, float); L /= np.linalg.norm(L)
    sh_ray = inter.intersects_id(loc + n * 0.05, np.tile(L, (len(loc), 1)), multiple_hits=False)[1]
    lit = np.ones(len(loc)); lit[sh_ray] = 0.45
    diff = np.clip((n * L).sum(1), 0, 1) * lit
    view = -dirs[ray]
    hv = (L + view) / np.linalg.norm(L + view, axis=1, keepdims=True)
    spec = np.clip((n * hv).sum(1), 0, 1) ** 40 * lit
    kind = ids[tri]
    base = np.zeros((len(loc), 3)); gloss = np.zeros(len(loc))
    for k, (c, g) in COLORS.items():
        base[kind == k] = c; gloss[kind == k] = g
    col = base * (0.50 + 0.65 * diff[:, None]) + (gloss * spec)[:, None]
    for k in emissive:
        col[kind == k] = COLORS[k][0]
    img[ray] = np.clip(col, 0, 1)
    plt.imsave(out, img.reshape(H, W, 3))
    print("ok", out)



inner = STL / "innen_unterteil.stl"
box_parts = {"box": [load(inner)]}
for item in json.loads((STL / "innen_bestueckung_demo.json").read_text()):
    box_parts.setdefault(item["kind"], []).append(
        rbox(item["w"], item["h"], item["d"], 1.0, item["x"], item["y"], item["z"]))
bb = load(inner).bounds
c = (bb[0] + bb[1]) / 2
render(box_parts, cam=(c[0] + 30, c[1] - 190, 330), target=(c[0], c[1], 8),
       out=IMG / "inneneinheit.png", size=(1400, 950), fov=42, light=(-0.3, 0.4, 0.85))
render({"box": [load(inner)]}, cam=(c[0], c[1] - 1, 420), target=(c[0], c[1], 0),
       out=IMG / "inneneinheit_leer.png", size=(1400, 900), fov=34, light=(-0.3, 0.4, 0.85))
