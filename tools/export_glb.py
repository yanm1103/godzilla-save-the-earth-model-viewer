#!/usr/bin/env python3
"""Bakes the monsters of Godzilla: Save the Earth (PS2) into the .glb files the site loads, in the layout of the
War of the Monsters Model Museum:

  public/models/<PREFIX><n>.glb        costume n: mesh, skeleton, texture, the idle clip ("idle") and, in the scene extras,
                                       the list of animations ({k, id, name, frames, file, first})
  public/models/<DIR>/aNNN.glb         one animation per file (only node names and keys); the site plays it on the costume
                                       (nodes are found by name) and merges them for the download (src/glbmerge.js)

usage:  python tools/export_glb.py <iso> [--out public/models] [--only Godzilla2k,Rodan] [--stats]

The ISO is read, nothing from the game is written next to the code: the output goes where --out says.

Conventions (same as the owner's WotM exporter):
- The game is Z up, facing +y, right handed. A root node rotates -90 degrees around X into glTF's Y up, so nothing inside it
  is mirrored: positions, normals and bone transforms are the game's own numbers.
- Skinning: 2 bones per vertex (weight of bone 0, the rest on bone 1). JOINTS_0 holds the skin bone index straight from the
  game; skin.joints[i] is the tree node of skin bone i. A rigid part (a whole submesh that follows one bone) is skinned
  100% to that bone.
- Bind pose = the nodes' own translation / rotation (rotations are stored inverted in the game: conjugated here).
- Animations keep the game's keys (LINEAR). A channel that stays at the bind pose is left out, so switching animations
  hands the node back to its bind value.
"""
import argparse
import json
import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reference', 'ste'))
import ste_model as S  # noqa: E402
import skeleton as K  # noqa: E402
import anim as A  # noqa: E402

ROOT_Q = [-math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)]   # -90 degrees around X: (x, y, z) -> (x, z, -y)
TOL = {'translation': 0.01, 'rotation': 5e-4}

# (prefix, display name, [(costume label, bundle file[, bundle whose animations it also plays])])
# A costume that plays another bundle's animations needs the same bone names and bind pose (checked: Godzilla 2000, Moguera;
# the nodes the costume lacks are skipped). Files not in the list are not monsters (scenery, HUD, effects).
MONSTERS = [
    ('GODZILLA2K', 'Godzilla 2000', [('low poly', 'Godzilla2k.cmp'), ('high poly', 'godzilla2k.bdp', 'Godzilla2k.cmp')]),
    ('GODZILLA90S', 'Godzilla 90s', [('', 'Godzilla90s.cmp')]),
    ('MECHAGODZILLA2', 'Mechagodzilla 2', [('', 'MechaGodzilla2.cmp')]),
    ('MECHAGODZILLA3', 'Mechagodzilla 3', [('', 'MechaGodzilla3.cmp')]),
    ('SPACEGODZILLA', 'SpaceGodzilla', [('default', 'SpaceGodzilla.cmp'), ('rail stage', 'spacegodzilla.bdp')]),
    ('ANGUIRUS', 'Anguirus', [('', 'Anguirus.cmp')]),
    ('BARAGON', 'Baragon', [('', 'Baragon.cmp')]),
    ('BIOLLANTE', 'Biollante', [('', 'Biollante.cmp')]),
    ('DESTOROYAH', 'Destoroyah', [('default', 'Destoroyah.cmp'), ('carnival', 'Destoroyah_Carnival.cmp')]),
    ('EBIRAH', 'Ebirah', [('default', 'Ebirah.cmp'), ('rail stage', 'ebirah.bdp')]),
    ('GHIDORAH', 'King Ghidorah', [('', 'Ghidorah.cmp')]),
    ('MGHIDORAH', 'Mecha-King Ghidorah', [('', 'MGhidorah.cmp')]),
    ('GIGAN', 'Gigan', [('', 'Gigan.cmp')]),
    ('JETJAGUAR', 'Jet Jaguar', [('default', 'JetJaguar.cmp'), ('carnival', 'JetJaguar_Carnival.cmp')]),
    ('MEGAGUIRUS', 'Megaguirus', [('', 'Megaguirus.cmp')]),
    ('MEGALON', 'Megalon', [('', 'Megalon.cmp')]),
    ('MOGUERA', 'Moguera', [('low poly', 'MOGUERA2.cmp'), ('high poly', 'moguera.bdp', 'MOGUERA2.cmp')]),
    ('MOTHRA', 'Mothra', [('', 'Mothra.cmp')]),
    ('MOTHRALARVAE', 'Mothra (larva)', [('', 'Mothra_Larvae.cmp')]),
    ('ORGA', 'Orga', [('', 'Orga.cmp')]),
    ('RODAN', 'Rodan', [('', 'Rodan.cmp')]),
]


# ---------------------------------------------------------------------------------------------------- glTF writer
class Glb:
    """Binary glTF 2.0 with a single buffer."""

    def __init__(self):
        self.bin = bytearray()
        self.j = {'asset': {'version': '2.0', 'generator': 'STE tools/export_glb.py'}, 'scene': 0, 'scenes': [{'nodes': []}],
                  'nodes': [], 'accessors': [], 'bufferViews': []}

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target:
            v['target'] = target
        self.bin += data
        self.j['bufferViews'].append(v)
        return len(self.j['bufferViews']) - 1

    def accessor(self, fmt, comps, values, ctype=5126, target=34962, minmax=False, normalized=False):
        flat = [x for v in values for x in (v if comps > 1 else (v,))]
        data = struct.pack('<%d%s' % (len(flat), fmt), *flat)
        a = {'bufferView': self.view(data, target), 'componentType': ctype, 'count': len(values),
             'type': {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4', 16: 'MAT4'}[comps]}
        if normalized:
            a['normalized'] = True
        if minmax:
            a['min'] = [min(v[k] for v in values) for k in range(comps)]
            a['max'] = [max(v[k] for v in values) for k in range(comps)]
        self.j['accessors'].append(a)
        return len(self.j['accessors']) - 1

    def node(self, d, parent=None):
        self.j['nodes'].append(d)
        i = len(self.j['nodes']) - 1
        if parent is not None:
            self.j['nodes'][parent].setdefault('children', []).append(i)
        return i

    def write(self, path):
        for k in ('accessors', 'bufferViews'):
            if not self.j[k]:
                del self.j[k]
        while len(self.bin) % 4:
            self.bin.append(0)
        if self.bin:
            self.j['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(self.j, separators=(',', ':')).encode()
        js += b' ' * ((-len(js)) % 4)
        out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + (8 + len(self.bin) if self.bin else 0))
        out += struct.pack('<II', len(js), 0x4E4F534A) + js
        if self.bin:
            out += struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(out)


def png_rgba(w, h, rgba):
    raw = b''.join(b'\x00' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))

    def ck(t, c):
        return struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + ck(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            ck(b'IDAT', zlib.compress(raw, 9)) + ck(b'IEND', b''))


def png_indexed(w, h, palette, idx):
    """8-bit indexed PNG: palette = 256 x (r, g, b, a); idx = w*h palette indices (the game's texture is indexed too)."""
    raw = b''.join(b'\x00' + idx[y * w:(y + 1) * w] for y in range(h))

    def ck(t, c):
        return struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c) & 0xffffffff)
    plte = b''.join(bytes(p[:3]) for p in palette)
    trns = bytes(p[3] for p in palette)
    out = b'\x89PNG\r\n\x1a\n' + ck(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 3, 0, 0, 0)) + ck(b'PLTE', plte)
    if any(a != 255 for a in trns):
        out += ck(b'tRNS', trns)
    return out + ck(b'IDAT', zlib.compress(raw, 9)) + ck(b'IEND', b'')


# ---------------------------------------------------------------------------------------------------- game data
def texture_indexed(b, tex):
    """(w, h, palette 256 x rgba, indices). Same decoding as ste_model.decode_texture, but it keeps the palette."""
    e, pe, w, h = tex
    t = b.tail_bytes(e)
    pal_raw = b.tail_bytes(pe)
    pal = [tuple(pal_raw[i * 4:i * 4 + 4]) for i in range(256)]
    p2 = list(pal)
    for g in range(0, 256, 32):                      # CSM1 palette swap: entries 8-15 <-> 16-23 of each group of 32
        for k in range(8):
            p2[g + 8 + k], p2[g + 16 + k] = pal[g + 16 + k], pal[g + 8 + k]
    # The alpha channel is not transparency here: Gigan, Jet Jaguar, Mecha-King Ghidorah have most of the body at low alpha and
    # the game draws them opaque. The body is exported opaque.
    p2 = [(r, g, bl, 255) for r, g, bl, _a in p2]
    return w, h, p2, S.unswizzle8(t[:w * h], w, h)


def rigid_bones(b, me):
    """{(nv, toff, size): bone hint}: the word right after a submesh block in the descriptor is, for a rigid part, the skin
    bone it follows (checked on MechaGodzilla2: left/right pairs of thighs, forearms and fingers, and the part sits at the
    bone's bind position)."""
    c = b.chunk(me)
    n = len(c) // 4
    w = struct.unpack_from('<%dI' % n, c, 0)
    subs = set(S.find_submeshes(b, me))
    out = {}
    for j in range(n - 6):
        key = (w[j], w[j + 4], w[j + 5])
        if key in subs and key not in out:
            out[key] = w[j + 6]
    return out


def decode_mesh(b, me):
    """ste_model.decode_mesh, with the bone of each rigid part fixed (the reference binds part i to bone i)."""
    m = S.decode_mesh(b, me)
    hints = rigid_bones(b, me)
    t = b.tail_bytes(me)
    base = 0
    m['rigid_parts'] = 0
    for (nv, toff, size) in S.find_submeshes(b, me):
        w4 = [struct.unpack_from('<I', t, toff + i * 16 + 12)[0] for i in range(nv)]
        if all(v in (0, 0x3f800000) for v in w4) and any(v == 0x3f800000 for v in w4):
            bone = hints.get((nv, toff, size), 0)
            m['rigid_parts'] += 1
            for i in range(base, base + nv):
                m['w0'][i], m['b0'][i], m['b1'][i] = 1.0, bone, bone
        base += nv
    return m


def unique_names(names):
    seen, out = {}, []
    for i, n in enumerate(names):
        n = n or 'node%d' % i
        if n in seen:
            seen[n] += 1
            n = '%s_%d' % (n, seen[n])
        else:
            seen[n] = 1
        out.append(n)
    return out


def conj(q):
    return (-q[0], -q[1], -q[2], q[3])


def normalize(q):
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return [c / n for c in q]


def inv_world(R, t):
    """Inverse of the rigid transform (R, t), as a column-major 4x4 for glTF."""
    Rt = [[R[c][r] for c in range(3)] for r in range(3)]
    ti = [-sum(Rt[r][c] * t[c] for c in range(3)) for r in range(3)]
    return [Rt[0][0], Rt[1][0], Rt[2][0], 0, Rt[0][1], Rt[1][1], Rt[2][1], 0, Rt[0][2], Rt[1][2], Rt[2][2], 0, ti[0], ti[1], ti[2], 1]


class Monster:
    """One bundle: its mesh, texture, skeleton and the animations that fit the skeleton."""

    def __init__(self, vol, fn):
        self.fn = fn
        self.b = S.Bundle(vol.get(fn))
        ms = self.b.meshes()
        if not ms:
            raise ValueError('%s: no mesh' % fn)
        self.me = ms[0]
        self.m = decode_mesh(self.b, self.me)
        self.sk = K.parse_skeleton(self.b, self.me)
        if not self.sk:
            raise ValueError('%s: no skeleton' % fn)
        self.names = unique_names(self.sk['name'])
        self.textures = self.b.textures()
        self.anims = self.load_animations()

    def borrow(self, other):
        """Also plays the animations of `other` (same bone names and bind pose). A name the costume already has stays its own."""
        own = {a['name'] for a in self.anims}
        fits = set(other.names) <= set(self.names)   # every bone the animation moves exists here: the file can be shared
        self.anims += [dict(a, shared=(other.fn, k) if fits else None) for k, a in enumerate(other.anims) if a['name'] not in own]

    def ensure_animation(self):
        """A bundle with no animation gets a still one (its bind pose), so the site has something to open."""
        if not self.anims:
            n = len(self.sk['parent'])
            self.anims = [dict(id=0, name='BIND_POSE', dur=1.0, src=self, tr=[[(0.0,) + tuple(t)] for t in self.sk['t']],
                               rot=[[(0.0,) + tuple(q)] for q in self.sk['q']])]

    def load_animations(self):
        b, sk = self.b, self.sk
        anims = [a for a in A.parse_animations(b, sk['name']) if a['nodes'] == sk['name']]
        entry = K.entry_names(b)
        out, used = [], {}
        for a in anims:
            name = a.get('name')
            if not name and a['id'] in entry:                       # the raw-float ones (.bdp) are not named by parse_animations
                name = entry[a['id']][1]
                if '_' in name:
                    name = name.split('_', 1)[1]
            name = (name or 'ANIM_%d' % a['id']).upper()
            used[name] = used.get(name, 0) + 1
            if used[name] > 1:
                name = '%s_%d' % (name, used[name])
            a['name'] = name
            a['src'] = self
            out.append(a)
        out.sort(key=lambda a: a['id'])
        return out


# ---------------------------------------------------------------------------------------------------- mesh glb
def build_costume(mon, out_path, anim_dir, listing):
    """Writes the costume's .glb. anim_dir: folder (inside the output) of the animation files; listing: their entries."""
    g = Glb()
    sk, m = mon.sk, mon.m
    n = len(sk['parent'])
    root = g.node({'name': 'STE', 'rotation': ROOT_Q})
    g.j['scenes'][0]['nodes'].append(root)

    # skeleton: one node per tree node, in tree order (index + 1 = glTF node)
    for i in range(n):
        g.node({'name': mon.names[i], 'translation': [float(x) for x in sk['t'][i]],
                'rotation': normalize(conj(sk['q'][i]))})
    for i in range(n):
        g.j['nodes'][root if sk['parent'][i] < 0 else 1 + sk['parent'][i]].setdefault('children', []).append(1 + i)

    # skin: joint i = skin bone i of the game
    W = K.world(sk, True)
    fallback = mon.names.index('Bip01 Pelvis') if 'Bip01 Pelvis' in mon.names else 0
    joints, ibm = [], []
    for nd in sk['skin']:
        nd = nd if nd >= 0 else fallback
        joints.append(1 + nd)
        ibm += inv_world(*W[nd])
    nb = len(joints)

    nv = len(m['pos'])
    pos = [tuple(p) for p in m['pos']]
    nrm = []
    for x, y, z in m['nrm']:
        ln = math.sqrt(x * x + y * y + z * z)
        nrm.append((x / ln, y / ln, z / ln) if ln > 1e-6 else (0.0, 0.0, 1.0))
    jnt, wgt = [], []
    for i in range(nv):
        b0, b1, w0 = m['b0'][i], m['b1'][i], m['w0'][i]
        if b0 >= nb:
            b0 = b1 if b1 < nb else 0
        if b1 >= nb:
            b1 = b0
        if b0 == b1:
            jnt.append((b0, 0, 0, 0)); wgt.append((1.0, 0.0, 0.0, 0.0))
        else:
            jnt.append((b0, b1, 0, 0)); wgt.append((w0, 1.0 - w0, 0.0, 0.0))
    tris = [i for t in m['tris'] for i in t]

    # texture
    tex = mon.textures[0]
    w, h, palette, idx = texture_indexed(mon.b, tex)
    image = g.view(png_indexed(w, h, palette, idx))
    g.j['images'] = [{'bufferView': image, 'mimeType': 'image/png', 'name': mon.fn.rsplit('.', 1)[0]}]
    g.j['samplers'] = [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}]
    g.j['textures'] = [{'sampler': 0, 'source': 0}]
    mat = {'name': 'skin', 'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}, 'metallicFactor': 0.0, 'roughnessFactor': 1.0},
           'doubleSided': True}
    g.j['materials'] = [mat]

    attrs = {'POSITION': g.accessor('f', 3, pos, minmax=True), 'NORMAL': g.accessor('f', 3, nrm),
             'TEXCOORD_0': g.accessor('f', 2, m['uv']), 'JOINTS_0': g.accessor('H', 4, jnt, ctype=5123),
             'WEIGHTS_0': g.accessor('f', 4, wgt)}
    ctype, fmt = (5123, 'H') if nv < 65536 else (5125, 'I')
    g.j['meshes'] = [{'name': 'body', 'primitives': [{'attributes': attrs, 'indices': g.accessor(fmt, 1, tris, ctype=ctype, target=34963),
                                                      'material': 0}]}]
    ib = g.accessor('f', 16, [ibm[k:k + 16] for k in range(0, len(ibm), 16)], target=None)
    g.j['skins'] = [{'name': 'skeleton', 'joints': joints, 'inverseBindMatrices': ib}]
    mesh_node = g.node({'name': 'body', 'mesh': 0, 'skin': 0}, root)

    # the idle goes inside this file (clip "idle"), every other animation in its own file
    idle = next((e for e in listing if e['name'] == 'NORMAL_IDLE'), listing[0] if listing else None)
    if idle:
        idle['first'] = True
        g.j['animations'] = [animation(g, mon, mon.anims[idle['k']], idle, node_map(mon, 1), name='idle')]
    g.j['scenes'][0]['extras'] = {'bones': nb, 'parts': m['rigid_parts'],
                                  'animations': [{k: v for k, v in e.items() if k != 'own'} for e in listing]}
    g.write(out_path)
    return mesh_node


# ---------------------------------------------------------------------------------------------------- animations
def reduce_const(vals, ref, tol):
    return all(max(abs(a - b) for a, b in zip(v, ref)) <= tol for v in vals)


def node_map(mon, offset):
    """Function: node index in the skeleton of an animation's own bundle -> glTF node of the costume `mon` (by bone name), or
    None when the costume has no such bone."""
    index = {n: i for i, n in enumerate(mon.names)}
    def node_of(src, i):
        j = index.get(src.names[i])
        return None if j is None else j + offset
    return lambda src: (lambda i: node_of(src, i))


def animation(gg, mon, a, entry, node_of, name=None):
    """glTF animation of `a` written into gg. node_of(src) -> function: the animation's own node index -> glTF node (or None).
    Keys are the game's own."""
    sk = a['src'].sk
    node_of = node_of(a['src'])
    dur = max(a['dur'], 1e-3)
    blob = bytearray()
    mine = []
    channels, samplers = [], []

    def acc(data, ctype, count, typ, **extra):
        while len(blob) % 4:
            blob.append(0)
        gg.j['accessors'].append(dict({'byteOffset': len(blob), 'componentType': ctype, 'count': count, 'type': typ}, **extra))
        blob.extend(data)
        mine.append(len(gg.j['accessors']) - 1)
        return mine[-1]

    def clean(times, vals):
        """Strictly increasing times starting at 0 (the game may repeat the last one); a lone key becomes a two-key hold."""
        ts, vs = [], []
        for t, v in zip(times, vals):
            if ts and t <= ts[-1] + 1e-6:
                vs[-1] = v          # same instant: the later key wins
                continue
            ts.append(t)
            vs.append(v)
        ts[0] = 0.0
        if len(ts) == 1:
            ts, vs = [0.0, dur], [vs[0], vs[0]]
        return ts, vs

    pending = []   # (node, path, times, values) of the tracks that leave the bind pose
    for i in range(len(sk['parent'])):
        if node_of(i) is None:
            continue
        tr, rot = a['tr'][i], a['rot'][i]
        vals = [list(k[1:]) for k in tr]
        if not reduce_const(vals, [float(x) for x in sk['t'][i]], TOL['translation']):
            pending.append((i, 'translation') + clean([k[0] * dur for k in tr], vals))
        vals, prev = [], None            # stored inverted: conjugate; each key in the hemisphere of the previous one
        for k in rot:
            q = normalize(conj(k[1:]))
            if prev is not None and sum(x * y for x, y in zip(prev, q)) < 0:
                q = [-c for c in q]
            vals.append(q)
            prev = q
        bind_q = normalize(conj(sk['q'][i]))
        if not (reduce_const(vals, bind_q, TOL['rotation']) or reduce_const(vals, [-c for c in bind_q], TOL['rotation'])):
            pending.append((i, 'rotation') + clean([k[0] * dur for k in rot], vals))

    # the clip lasts as long as its longest track: make sure one track reaches the duration
    if not pending:   # nothing moves: a still pose lasting `dur`
        first = next(i for i in range(len(sk['parent'])) if node_of(i) is not None)
        pending.append((first, 'rotation', [0.0, dur], [normalize(conj(sk['q'][first]))] * 2))
    elif max(p[2][-1] for p in pending) < dur - 1e-4:
        i, path, ts, vs = pending[0]
        pending[0] = (i, path, ts + [dur], vs + [vs[-1]])

    inputs = {}
    for i, path, ts, vs in pending:
        key = tuple(ts)
        if key not in inputs:
            inputs[key] = acc(struct.pack('<%df' % len(ts), *ts), 5126, len(ts), 'SCALAR', min=[ts[0]], max=[ts[-1]])
        flat = [x for v in vs for x in v]
        if path == 'rotation':
            q16 = [max(-32767, min(32767, round(x * 32767))) for x in flat]
            out = acc(struct.pack('<%dh' % len(q16), *q16), 5122, len(vs), 'VEC4', normalized=True)
        else:
            out = acc(struct.pack('<%df' % len(flat), *flat), 5126, len(vs), 'VEC3')
        samplers.append({'input': inputs[key], 'output': out, 'interpolation': 'LINEAR'})
        channels.append({'sampler': len(samplers) - 1, 'target': {'node': node_of(i), 'path': path}})
    bv = gg.view(bytes(blob))
    for x in mine:
        gg.j['accessors'][x]['bufferView'] = bv
    return {'name': name or entry['name'], 'channels': channels, 'samplers': samplers,
            'extras': {'k': entry['k'], 'id': entry['id'], 'frames': entry['frames'], 'dur': dur}}


def write_animations(mon, out_dir, anim_dir, listing):
    """One .glb per animation, with only node names and keys."""
    for e in listing:
        if not e['own']:
            continue
        a = mon.anims[e['k']]
        gg = Glb()
        gg.j['nodes'] = [{'name': nm} for nm in mon.names]
        gg.j['scenes'][0]['nodes'] = list(range(len(mon.names)))
        gg.j['animations'] = [animation(gg, mon, a, e, node_map(mon, 0))]
        gg.write(os.path.join(out_dir, e['file']))


def listing_of(mon, anim_dir, dirs):
    """dirs: {bundle file: folder of its animation files} of the costumes already written."""
    out = []
    for k, a in enumerate(mon.anims):
        shared = a.get('shared')
        e = {'k': k, 'id': a['id'], 'name': a['name'], 'frames': round(a['dur'] * FPS) + 1,
             'file': '%s/a%03d.glb' % (dirs[shared[0]], shared[1]) if shared and shared[0] in dirs else '%s/a%03d.glb' % (anim_dir, k)}
        e['own'] = e['file'].startswith(anim_dir + '/')
        out.append(e)
    return out


FPS = 30

# Portraits of the monster select screen: ShellCommon.bdp has "<name>face" textures, 64x56 RGBA32 in raster order (the picture
# is the top 64x52). Ebirah is not playable and has none.
FACES = {'GODZILLA2K': 'godzilla2kface', 'GODZILLA90S': 'godzilla90sface', 'MECHAGODZILLA2': 'mechagodzilla2face',
         'MECHAGODZILLA3': 'mechagodzilla3face', 'SPACEGODZILLA': 'spacegodzillaface', 'ANGUIRUS': 'anguirusface',
         'BARAGON': 'baragonface', 'BIOLLANTE': 'biollanteface', 'DESTOROYAH': 'destoroyahface', 'GHIDORAH': 'ghidorahface',
         'MGHIDORAH': 'mghidorahface', 'GIGAN': 'giganface', 'JETJAGUAR': 'jetjaguarface', 'MEGAGUIRUS': 'megaguirusface',
         'MEGALON': 'megalonface', 'MOGUERA': 'moguera2face', 'MOTHRA': 'mothraface', 'MOTHRALARVAE': 'mothra_larvaeface',
         'ORGA': 'orgaface', 'RODAN': 'rodanface'}


def export_logos(vol, out_dir, only=None):
    """public/logos/<prefix lowercase>.png, 64x52 with the game's alpha (0..0x80 -> 0..255)."""
    b = S.Bundle(vol.get('ShellCommon.bdp'))
    names = K.entry_names(b)
    entries = {names[e['id']][1].lower(): e for e in b.entries if e['id'] in names}
    for prefix, face in FACES.items():
        if only and prefix not in only:
            continue
        t = b.tail_bytes(entries[face])
        px = bytearray()
        for k in range(0, 64 * 52 * 4, 4):
            px += bytes((t[k], t[k + 1], t[k + 2], min(255, t[k + 3] * 2)))
        path = os.path.join(out_dir, '..', 'logos', prefix.lower() + '.png')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(png_rgba(64, 52, bytes(px)))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('iso')
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'public', 'models'))
    ap.add_argument('--only', help='comma separated prefixes (GODZILLA2K,RODAN)')
    args = ap.parse_args(argv)
    vol = S.Vol(S.Iso(args.iso))
    only = {s.upper() for s in args.only.split(',')} if args.only else None
    export_logos(vol, args.out, only)
    catalog = []
    for prefix, name, costumes in MONSTERS:
        if only and prefix not in only:
            continue
        labels, made, dirs = [], [], {}
        for label, fn, *borrow in costumes:
            try:
                mon = Monster(vol, fn)
                for other in borrow:
                    mon.borrow(Monster(vol, other))
                mon.ensure_animation()
            except Exception as ex:
                print('skip %s: %s' % (fn, ex))
                continue
            ci = len(made)
            anim_dir = prefix if ci == 0 else '%s_%d' % (prefix, ci)
            listing = listing_of(mon, anim_dir, dirs)
            dirs[fn] = anim_dir
            build_costume(mon, os.path.join(args.out, '%s%d.glb' % (prefix, ci)), anim_dir, listing)
            write_animations(mon, args.out, anim_dir, listing)
            made.append(ci)
            labels.append(label)
            print('%-15s %-22s %5d v %5d tris %3d bones %2d rigid  %3d anims  tex %s' % (
                prefix + str(ci), fn, len(mon.m['pos']), len(mon.m['tris']), len(mon.sk['skin']), mon.m['rigid_parts'],
                len(listing), [(w, h) for _, _, w, h in mon.textures]))
        catalog.append((prefix, name, made, labels))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
