// Puts every animation into one .glb for the download. The costume's .glb carries mesh, skeleton and one animation; each
// other animation is its own small .glb (only node names and keys). This copies each animation's accessors and binary data
// into the costume's file and points its channels at the costume's nodes by name, so the mesh, textures and extras stay
// byte for byte as exported.

const MAGIC = 0x46546c67; // "glTF"
const JSON_CHUNK = 0x4e4f534a;
const BIN_CHUNK = 0x004e4942;

function readGlb(buffer) {
  const view = new DataView(buffer);
  if (view.getUint32(0, true) !== MAGIC) throw new Error("not a .glb");
  let json = null;
  let bin = new Uint8Array(0);
  for (let o = 12; o < view.byteLength; ) {
    const length = view.getUint32(o, true);
    const type = view.getUint32(o + 4, true);
    const data = new Uint8Array(buffer, o + 8, length);
    if (type === JSON_CHUNK) json = JSON.parse(new TextDecoder().decode(data));
    else if (type === BIN_CHUNK) bin = data;
    o += 8 + length;
  }
  if (!json) throw new Error(".glb without JSON");
  if ((json.buffers?.length ?? 0) > 1) throw new Error(".glb with more than one buffer");
  return { json, bin };
}

function writeGlb(json, bin) {
  const pad4 = (n) => (n + 3) & ~3;
  const text = new TextEncoder().encode(JSON.stringify(json));
  const jsonLength = pad4(text.length);
  const binLength = pad4(bin.length);
  const total = 12 + 8 + jsonLength + (bin.length ? 8 + binLength : 0);
  const out = new Uint8Array(total);
  const view = new DataView(out.buffer);
  view.setUint32(0, MAGIC, true);
  view.setUint32(4, 2, true);
  view.setUint32(8, total, true);
  view.setUint32(12, jsonLength, true);
  view.setUint32(16, JSON_CHUNK, true);
  out.set(text, 20);
  out.fill(0x20, 20 + text.length, 20 + jsonLength); // the JSON chunk is padded with spaces
  if (bin.length) {
    const o = 20 + jsonLength;
    view.setUint32(o, binLength, true);
    view.setUint32(o + 4, BIN_CHUNK, true);
    out.set(bin, o + 8); // the BIN chunk with zeros (already 0)
  }
  return out;
}

// base: the costume's .glb, animations: the animation .glb files in the order they go in the file (ArrayBuffers).
// Returns the new .glb (Uint8Array).
export function mergeGlb(base, animations) {
  const { json, bin: baseBin } = readGlb(base);
  json.accessors ??= [];
  json.bufferViews ??= [];
  json.animations ??= [];

  const nodeByName = new Map(json.nodes.map((n, i) => [n.name, i]));
  const parts = [baseBin];
  let size = baseBin.length;

  for (const buffer of animations) {
    const { json: a, bin } = readGlb(buffer);
    size = (size + 3) & ~3; // accessors of floats start on a multiple of 4
    const binOffset = size;
    parts.push({ offset: binOffset, bin });
    size += bin.length;

    const viewBase = json.bufferViews.length;
    for (const v of a.bufferViews ?? []) json.bufferViews.push({ ...v, buffer: 0, byteOffset: (v.byteOffset ?? 0) + binOffset });
    const accBase = json.accessors.length;
    for (const acc of a.accessors ?? []) {
      json.accessors.push(acc.bufferView === undefined ? { ...acc } : { ...acc, bufferView: acc.bufferView + viewBase });
    }
    for (const anim of a.animations ?? []) {
      const channels = [];
      for (const ch of anim.channels) {
        const node = nodeByName.get(a.nodes[ch.target.node]?.name);
        if (node === undefined) continue; // a node the model doesn't have: nothing to move
        channels.push({ ...ch, target: { ...ch.target, node } });
      }
      if (!channels.length) continue;
      const samplers = anim.samplers.map((s) => ({ ...s, input: s.input + accBase, output: s.output + accBase }));
      json.animations.push({ ...anim, channels, samplers });
    }
  }

  const bin = new Uint8Array(size);
  bin.set(baseBin, 0);
  for (const p of parts.slice(1)) bin.set(p.bin, p.offset);
  if (json.buffers?.length) json.buffers[0].byteLength = size;
  else json.buffers = [{ byteLength: size }];
  return writeGlb(json, bin);
}
