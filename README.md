# Godzilla: Save the Earth Model Viewer

A browser 3D viewer for the monsters of *Godzilla: Save the Earth* (PS2): meshes, textures, skeletons and the ~150 named
animations of each monster. A fan project by TwistZero, built the same way as the
[War of the Monsters Model Museum](https://github.com/yanm1103/wotm-model-museum) (Vite + three.js, same layout).

Site: <https://yanm1103.github.io/godzilla-save-the-earth-model-viewer/>

## Run it

```
npm install
npm run dev        # http://localhost:5173
npm run build      # dist/, what GitHub Pages serves (the workflow does it on every push to master)
```

## Where the models come from

`public/models/` holds the baked `.glb` files (one per costume, plus one small file per animation in `public/models/<PREFIX>/`).
They are made from the game disc by `tools/export_glb.py`, which uses the decoders in `reference/ste/`
(format notes in `reference/FORMATS.md`):

```
python tools/export_glb.py "<path to SLUS_208.09 iso>"            # all monsters, into public/models
python tools/export_glb.py "<iso>" --only GODZILLA2K,RODAN         # some of them
```

Python 3, no packages needed. The ISO and the raw game files (`.cmp`, `.bdp`, `GODZILLA.VOL`) never go in this repo;
only the baked output does.

What the exporter does, in short: mesh with 2-bone skinning (rigid parts follow the bone the game assigns them), one opaque
texture, the Biped skeleton, every animation with the game's own name (`NORMAL_IDLE` is the idle), the game's keys as they are.
The game is Z up; a root node rotates it into glTF's Y up.

Costumes: Godzilla 2000 and Moguera have the low poly model of the fight and the higher poly one of the rail (water) stages;
the high poly one plays the same fight animations as the low poly one plus its own. Destoroyah and Jet Jaguar have a
carnival version. Ebirah and SpaceGodzilla have a "rail stage" model with no animation of its own (shown in its bind pose).

## Not done

- Monster logos (the HUD textures `hud<name>.bdp` are in another format than the model textures and are not decoded).
- Effect textures (halos, noise), sounds and the scenery.
