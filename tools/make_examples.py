#!/usr/bin/env python3
"""Generate the example models and scenes in examples/.

Models are thin surfaces authored in centimetres, Y up — deliberately coarse, so the
app's remeshing (step 02) does the work:

    hexagon-panel.obj   flat hexagon, 300 cm across
    star-panel.fbx      flat five-pointed star (ASCII FBX 7.4)
    ring-band.obj       open cylindrical band, 240 cm wide, 70 cm tall
    plan-web.dxf        2D line plan in millimetres (lines, circle, arcs, polyline, spline)

Scenes place them, pin anchors and give the cloth slack. Anchor positions only need
to be close: the app snaps each to the nearest particle.

    python3 tools/make_examples.py
"""
import json
import math
import os

OUT = os.path.join(os.path.dirname(__file__), '..', 'examples')
SIZE = 3.0                      # the app scales imports to this largest dimension


# --- geometry ----------------------------------------------------------------

def polygon_fan(outline):
    """Flat polygon in the XZ plane as a centre fan. Returns (verts, tris)."""
    verts = [(0.0, 0.0, 0.0)] + [(x, 0.0, z) for x, z in outline]
    n = len(outline)
    tris = [(0, 1 + (i + 1) % n, 1 + i) for i in range(n)]   # counter-clockwise from above
    return verts, tris


def hexagon_panel():
    R = 150.0
    return polygon_fan([(R * math.cos(math.radians(60 * k)), R * math.sin(math.radians(60 * k))) for k in range(6)])


def star_panel():
    ro, ri = 150.0, 62.0
    pts = []
    for k in range(10):
        a = math.radians(90 + 36 * k)
        r = ro if k % 2 == 0 else ri
        pts.append((r * math.cos(a), r * math.sin(a)))
    return polygon_fan(pts)


def ring_band():
    R, H, n = 120.0, 70.0, 24
    verts, tris = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        verts += [(R * math.cos(a), 0.0, R * math.sin(a)), (R * math.cos(a), H, R * math.sin(a))]
    for k in range(n):
        a0, a1 = 2 * k, 2 * ((k + 1) % n)
        tris += [(a0, a1, a0 + 1), (a1, a1 + 1, a0 + 1)]
    return verts, tris


# --- writers -------------------------------------------------------------------

def write_obj(path, name, verts, tris):
    with open(path, 'w') as f:
        f.write(f'# {name} — hanging-lab example model (cm, Y up)\n')
        f.write(f'o {name}\n')
        for v in verts:
            f.write('v {:.3f} {:.3f} {:.3f}\n'.format(*v))
        for t in tris:
            f.write('f {} {} {}\n'.format(*(i + 1 for i in t)))


def looks_ascii_to_three(text):
    """Mirror of FBXLoader's isFbxFormatASCII: it samples characters at the triangular
    numbers 0, 1, 3, 6, … and calls the file binary if any matches 'Kaydara\\FBX\\Binary\\\\'."""
    magic = 'Kaydara\\FBX\\Binary\\\\'
    pos = 0
    for i, ch in enumerate(magic):
        if pos < len(text) and text[pos] == ch:
            return False
        pos += i + 1
    return True


def write_fbx(path, name, verts, tris):
    vs = ','.join(f'{c:.3f}' for v in verts for c in v)
    idx = ','.join(f'{a},{b},{-c - 1}' for a, b, c in tris)
    text = f'''; FBX 7.4.0 project file
; ----------------------------------------------------
FBXHeaderExtension:  {{
	FBXHeaderVersion: 1003
	FBXVersion: 7400
	Creator: "hanging-lab tools/make_examples.py"
}}
GlobalSettings:  {{
	Version: 1000
	Properties70:  {{
		P: "UpAxis", "int", "Integer", "",1
		P: "UnitScaleFactor", "double", "Number", "",1
	}}
}}
Objects:  {{
	Geometry: 1000, "Geometry::{name}", "Mesh" {{
		Vertices: *{len(verts) * 3} {{
			a: {vs}
		}}
		PolygonVertexIndex: *{len(tris) * 3} {{
			a: {idx}
		}}
		GeometryVersion: 124
	}}
	Model: 2000, "Model::{name}", "Mesh" {{
		Version: 232
		Properties70:  {{
		}}
	}}
}}
Connections:  {{
	C: "OO",2000,0
	C: "OO",1000,2000
}}
'''
    assert looks_ascii_to_three(text), path
    with open(path, 'w') as f:
        f.write(text)


# --- scenes --------------------------------------------------------------------

def normalise(verts):
    """(centre, scale) of the app's import: bbox centre to origin, largest side = SIZE."""
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    return centre, SIZE / max(b - a for a, b in zip(lo, hi))


def world(verts, p, position):
    c, s = normalise(verts)
    return [round((p[i] - c[i]) * s + position[i], 3) for i in range(3)]


def anchor(verts, p, position, gather=1.0):
    at = world(verts, p, position)
    if gather == 1.0:
        return at
    # slide horizontally toward the object's centre line
    return {'at': at, 'to': [round(position[0] + (at[0] - position[0]) * gather, 3), at[1],
                             round(position[2] + (at[2] - position[2]) * gather, 3)]}


def scene(obj, params, display='both'):
    return {'format': 'hanging-lab', 'version': 1, 'params': params, 'display': display, 'objects': [obj]}


def hex_scene(verts):
    pos = [0, 4.4, 0]
    corners = verts[1:]
    return scene({
        'name': 'Hexagon panel', 'source': {'src': 'hexagon-panel.obj', 'format': 'obj', 'size': SIZE},
        'position': pos, 'cloth': {'resolution': 30},
        'anchors': [anchor(verts, p, pos, 0.76) for p in corners],
    }, {'stretch': 0.5, 'bending': 0.12})


def star_scene(verts):
    pos = [0, 4.4, 0]
    tips = verts[1::2]                      # outline starts at a tip, alternates tip / notch
    return scene({
        'name': 'Star panel', 'source': {'src': 'star-panel.fbx', 'format': 'fbx', 'size': SIZE},
        'position': pos, 'cloth': {'resolution': 34},
        'anchors': [anchor(verts, p, pos, 0.8) for p in tips],
    }, {'stretch': 0.5, 'bending': 0.1})


def ring_scene(verts):
    pos = [0, 4.0, 0]
    top = [v for v in verts if v[1] > 0]
    picks = top[0::3]                       # every third top-rim vertex: 8 suspension points
    return scene({
        'name': 'Ring band', 'source': {'src': 'ring-band.obj', 'format': 'obj', 'size': SIZE},
        'position': pos, 'cloth': {'resolution': 30},
        'anchors': [anchor(verts, p, pos, 0.9) for p in picks],
        'loads': [world(verts, v, pos) + [0.04] for v in [w for w in verts if w[1] == 0][1::4]],
    }, {'stretch': 0.45, 'bending': 0.2})


# --- 2D line drawing ----------------------------------------------------------

def plan_web_dxf():
    """A plan of a hanging web in millimetres, as an architect would draw it: twelve
    spokes (LINE) reaching to the supports, a ring (CIRCLE), an inner ring of ARCs, a
    wavy LWPOLYLINE with bulges and one SPLINE — every entity type the importer reads."""
    R_ring, R_out, R_in = 4200.0, 6000.0, 1800.0
    out = ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1009', '9', '$INSUNITS', '70', '4', '0', 'ENDSEC',
           '0', 'SECTION', '2', 'ENTITIES']
    def ent(kind, *codes):
        out.extend(['0', kind, '8', 'WEB'])
        out.extend(str(c) for c in codes)
    for k in range(12):
        a = math.radians(30 * k)
        ent('LINE', 10, 0.0, 20, 0.0, 30, 0.0, 11, round(R_out * math.cos(a), 3), 21, round(R_out * math.sin(a), 3), 31, 0.0)
    ent('CIRCLE', 10, 0.0, 20, 0.0, 30, 0.0, 40, R_ring)
    for k in range(6):                                   # inner ring as six arcs of 60°
        ent('ARC', 10, 0.0, 20, 0.0, 30, 0.0, 40, R_in, 50, 60 * k, 51, 60 * k + 60)
    # a wavy ring between the two: 12 vertices on the spokes, alternate bulges
    pts = [(3000 * math.cos(math.radians(30 * k)), 3000 * math.sin(math.radians(30 * k))) for k in range(12)]
    codes = [90, 12, 70, 1]
    for k, (x, y) in enumerate(pts):
        codes += [10, round(x, 3), 20, round(y, 3), 42, 0.25 if k % 2 else -0.25]
    ent('LWPOLYLINE', *codes)
    # one spline (clamped cubic) bridging two spoke ends of the outer ring
    ctrl = [(R_ring, 0), (5200, 1600), (4800, 3400), (R_ring * math.cos(math.radians(60)), R_ring * math.sin(math.radians(60)))]
    codes = [70, 8, 71, 3, 72, 8, 73, 4]
    for kv in [0, 0, 0, 0, 1, 1, 1, 1]:
        codes += [40, kv]
    for x, y in ctrl:
        codes += [10, round(x, 3), 20, round(y, 3), 30, 0.0]
    ent('SPLINE', *codes)
    out += ['0', 'ENDSEC', '0', 'EOF']
    return '\n'.join(out) + '\n', R_out


def plan_web_scene(R_out):
    """Hang the plan from the outer ends of its spokes; a sachet on the centre."""
    pos, s = [0, 4.6, 0], SIZE / (2 * R_out)
    ends = [[round(R_out * s * math.cos(math.radians(30 * k)), 3), pos[1], round(-R_out * s * math.sin(math.radians(30 * k)), 3)]
            for k in range(12)]
    return {'format': 'hanging-lab', 'version': 1, 'params': {'stretch': 0, 'bending': 0, 'damping': 2}, 'display': 'net',
            'objects': [{'name': 'Plan web', 'source': {'src': 'plan-web.dxf', 'format': 'dxf', 'size': SIZE},
                         'position': pos, 'cloth': {'resolution': 50, 'slack': 1.12},
                         'anchors': ends, 'loads': [[0, pos[1], 0, 0.25]]}]}


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    hv, ht = hexagon_panel()
    sv, st = star_panel()
    rv, rt = ring_band()
    write_obj(os.path.join(OUT, 'hexagon-panel.obj'), 'hexagon_panel', hv, ht)
    write_fbx(os.path.join(OUT, 'star-panel.fbx'), 'star_panel', sv, st)
    write_obj(os.path.join(OUT, 'ring-band.obj'), 'ring_band', rv, rt)
    dxf, r_out = plan_web_dxf()
    with open(os.path.join(OUT, 'plan-web.dxf'), 'w') as f:
        f.write(dxf)
    for name, data in [('hex-shell', hex_scene(hv)), ('star-canopy', star_scene(sv)), ('ring-band', ring_scene(rv)),
                       ('plan-web', plan_web_scene(r_out))]:
        with open(os.path.join(OUT, name + '.json'), 'w') as f:
            json.dump(data, f, indent=1)
    print('wrote', sorted(os.listdir(OUT)))
