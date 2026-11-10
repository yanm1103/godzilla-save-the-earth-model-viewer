# Godzilla: Save the Earth (PS2) file formats, as far as they are decoded

Everything here is implemented in `reference/ste/*.py`; the code is the authority, this is the map. All integers are little
endian. The ELF (`SLUS_208.09`) is stripped (Metrowerks compiler) and was not needed: the data formats were read from the files.

## Container

- ISO9660 -> `GODZILLA.VOL` (PVOL, ~734 MB, 483 files). Header 16 bytes (`PVOL`, 0x1001, N, ?), then N entries of 12 bytes
  `{offset, size, idx}` (offset from the start of the VOL), then `u32 N` + N name offsets (relative to that `u32`), ASCII names.
  The name of an entry is `offsets[idx]`.
- Per monster: `<Name>.zip` (deflate, holds only the `.cmp`), `<Name>.cmp` (low-poly mesh, texture, skeleton, ~150 compressed
  animations), sometimes `<name>.bdp` (high-poly mesh and raw-float animations), `hud<name>.bdp`, `<name>.mic` (music/voice),
  `AM<Name>.bsf` (move scripts). Sounds: `godzilla_sound.samp/.uber`, `godzilla_voice_e/j.samp/.uber`, `eff.hd/.bd`.
  23 `.cmp` files carry monsters (two are "carnival" variants).

## Pipeworks Bundle File version 1.3 (`.cmp`, `.bdp`)

- `u32@0x68` = start of the data ("base"); `u32@0x70` / `@0x74` = start / size of the "tail", the raw PS2 data (vertex streams,
  texture pixels, palettes).
- TOC at `0x78`, 18-byte entries `{u16 id, u32 off (from base), u32 size, u32 tailOff, u32 tailSize}` until `id == 0xffff`.
- After the TOC: a name table (`u32 N` + N offsets relative to that `u32`, NUL terminated strings; `.cmp` names have a
  `<control char>000` prefix, strip it). The names are sorted, **but entries are not named by position**:
- After the last string (and its `0xff` padding) up to `base`: one 16-byte record per entry
  `{u16 entryId, u16 type, u32 nameIndex, u32 n, u32 extra}`. Type 4 = animation. **This is the entry -> name map.**
  (Matching names to animations by alphabetical order gave the right counts and the wrong names.)

## Mesh

- Descriptor entry: `u16 nSub, u16 nBones`, then `nBones x u32` = name index of skin bone `i`. Further in the descriptor, blocks
  `{nv, nb, flags, 0, tailOff, size}` (one per submesh; found by scanning the descriptor and validating, see `find_submeshes`).
- Streams of a submesh in the tail: positions `nv x 16 B`, normals `nv x 4 B` (`s8 x,y,z` + flag), UVs `nv x 4 B`
  (`u16 u, v`, /4096) that **start at `tailOff + align16(nv*20)`**.
- **Skinned vertex:** `float x,y,z`, `u16 weight/4096`, `u8 bone0`, `u8 bone1`; the "draw" flag is byte 3 of the normal (0x7f).
  Weight is bone 0's, the rest is bone 1's.
- **Rigid vertex** (a whole submesh): `float x,y,z` + `float 0.0 / 1.0` (the draw flag); no bones; one submesh = one part of
  one bone. The bone of each part is **not decoded yet**. MechaGodzilla2 is entirely rigid.
- Triangle strips: triangle `(i-2, i-1, i)` exists iff vertex `i` has the draw flag; swap the first two indices for odd `i`.
- Axes: Z up, the monster faces +y, right handed. Bind pose in model space.

## Texture

PSMT8 (8-bit indexed), usually 256x256 (some 512x512), mip chain after the base level, in the tail; the palette (256 x RGBA) is
the next TOC entry. Descriptor `u32 3, 0x40000013, u16 w, u16 h`. PS2 palette swap (CSM1: swap entries 8-15 with 16-23 in each
group of 32); alpha is 0..0x80, multiply by 2. Unswizzle: treat the data as PSMCT32 of width `w/2`:
`blk=(y&~0xf)*w+(x&~0xf)*2; sw=(((y+2)>>2)&1)*4; py=(((y&~3)>>1)+(y&1))&7; col=py*w*2+((x+sw)&7)*4; bn=((y>>1)&1)+((x>>2)&2)`.
(Using `~0x1f` for the x mask scrambles the texture in vertical slices.)

## Skeleton

- **Tree entry** (`u32@0x1c == 0x40`, `u32@0x20` = node count): records `{idx, parent (0xffffffff = root), nChildren, nameIndex,
  child offsets...}` from `0x40`, offsets absolute inside the entry.
- **Pose entry** (the next one): `u32@0x2c` = n, per-node record offsets at `0x38 + 4*i`; a node record has its translation
  (3 floats) and quaternion `x,y,z,w` at the offsets stored in `+0x1c` / `+0x20`.
- **The quaternions are stored inverted** (use the conjugate). World matrix = parent world * local, with the conjugated rotation.
  Checked by comparing, per bone, the node position with the centroid of the vertices it moves (error 5-19 units on a ~100 unit
  monster; 69 without the conjugate).
- Bones are named like 3ds Max Biped (`Bip01 L Thigh`...). Many monsters add their own (wings, tentacles, pincers).

## Animations

- `.bdp` (raw floats): a triple of entries {tree, data, a 0x38-byte record `{0, treeId, dataId}`}. Data: `f32@0x1c` = duration (s),
  `u32@0x24` = size, `u32@0x2c` = node count, record offsets at `0x38 + 4*i`. Node record: `+8` translation key count, `+0xc`
  rotation key count, `+0x1c/+0x20` offsets of the lists. Translation key 24 B (`x,y,z, dx,dy,dz`), rotation key 36 B
  (`x,y,z,w` + 4 floats of delta + pad). Uniform sampling at 30 fps; one key = the bone does not move.
  The 17 of `godzilla2k.bdp` are **swimming** loops (the high-poly Godzilla is the water-stage model).
- `.cmp` (compressed, 122-171 per monster): entry header `{0,1,1,6}`, `u32@0x20 == 2`; `f32@0x1c` duration; `u32@0x2c` node count
  (index = tree node); `u32@0x38` start of the translation stream; `u32@0x3c` start of the rotation stream. Both streams have one
  block per node, in node order, and end exactly at the end of the entry (a good check).
  - **Translation:** `3 floats` (max |value| per axis) + `{node, A, B, 0}` + `A` keys `{u16 t, s16 cx, cy, cz}`;
    position = `c / 32767 * max` (the sign lives in `c`).
  - **Rotation:** `{node, N, 0, 0}` + 6 bytes (`s16 x,y,z` of key 0, t = 0) + `N-1` x `{u16 t, s16 x,y,z}`;
    `w = sqrt(1 - x^2 - y^2 - z^2)`. `t / 65534` = fraction of the duration (`0xfffe` = end). Same conjugate convention.
- Names: see the entry -> name map in "Pipeworks Bundle". Examples for Godzilla 2000: `WALK` 1.07 s, `RUN` 0.97 s,
  `NORMAL_IDLE` 1.17 s, `VICTORY` 4.63 s, `ATOMICBREATH_CHARGE_FULL` 3.33 s, `KOED_FACEUP_IDLE` 3.33 s.

## Not decoded

Sounds (`.samp/.uber`, `.mic`), the bone of each rigid part (see Mesh), effect textures, scenery textures beyond the first,
`AM*.bsf` move scripts, the two overlays `OVRLY1/2.OVL`.
