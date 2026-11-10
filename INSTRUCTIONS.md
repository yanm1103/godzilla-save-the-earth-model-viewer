# Instructions for Claude: build the Godzilla: Save the Earth Model Viewer

Owner: TwistZero (GitHub `yanm1103`). The owner writes Portuguese: **talk to them in Portuguese**. Code and docs in English,
commit messages in Portuguese.

## What this is

A browser 3D viewer of every monster in **Godzilla: Save the Earth** (PS2, NTSC-U `SLUS_208.09`, by Pipeworks): mesh, texture,
skeleton and the ~150 named animations of each monster.

It is a **copy of the owner's own project, the War of the Monsters Model Museum**
(site <https://yanm1103.github.io/wotm-model-museum/>, repo <https://github.com/yanm1103/wotm-model-museum>): same stack
(Vite + three.js), same layout, same look, same GitHub Pages deploy. Copy it as is and change only what this game needs.
Do not redesign anything.

## What already exists here

`reference/ste/` is working Python, written while reverse engineering the game. It reads the ISO and decodes everything.
`reference/FORMATS.md` documents the file formats. Read both before writing anything. They are the reference implementation:
port or reuse them, do not rediscover the formats.

| file | what it does |
|---|---|
| `ste_model.py` | ISO9660 -> `GODZILLA.VOL` -> Pipeworks bundle -> mesh, texture (PS2 swizzle, palette) |
| `skeleton.py` | name table, bone tree, bind pose (translation + quaternion), entry -> name table |
| `anim.py` | animations: raw floats (`.bdp`) and the compressed ones (`.cmp`), with their real names |
| `gen_viewer.py` + `viewer_template.html` | a first, standalone WebGL viewer (28 models, plays animations). Proof that the data is right; **not** the final site |
| `export_dae.py` | exports one monster as Collada: shows how vertex weights and the bind matrices are assembled |

The owner's ISO is on their machine: `D:\Roms\PS2SMB\DVD\SLUS_208.09.GODZILLA - SAVE THE EARTH.iso`. Pass it as an argument.

## Steps

1. **Copy the template.** Clone the museum repo into a temp folder and copy into this repo: `index.html`, `package.json`,
   `package-lock.json`, `vite.config.js`, `.github/workflows/deploy.yml`, `src/main.js`, `src/glbmerge.js`, `src/catalog.js`,
   `src/style.css`. Read `src/main.js` and `src/catalog.js` first: they are the contract with the `.glb` files.
   Do **not** copy: `public/models`, `public/stages`, `public/logos`, `public/fx`, `docs/screenshots`, `WOTMMM.*`, `og.jpg`,
   `src/anim-ids.json`, `scripts/anim-ids.mjs`, `VIEWER_WEB.md` (all War of the Monsters specific). `src/effects.js` is the
   WotM fireball and lens flare: leave it out unless something in `main.js` needs it, and then stub it.
2. **Rebrand.** Title "Godzilla: Save the Earth Model Viewer", the description, the `og:` tags and the URLs
   (`https://yanm1103.github.io/godzilla-save-the-earth-model-viewer/`), `package.json` name. Keep "Fan project by TwistZero"
   and the ko-fi button. Remove the stage picker and the stage background (this game has no such thing to show).
3. **Bake the models** (the real work). Write `tools/export_glb.py`: it takes the ISO and writes, in the museum's layout,
   `public/models/<KEY>.glb` (mesh, skeleton, idle animation, list of animations) and `public/models/<KEY>/aNNN.glb` (one
   animation per file; the site merges them with `src/glbmerge.js`).
   - Learn the exact glTF conventions from the owner's WotM exporter: `tools/monglb.py` and `tools/gltf.py` in
     <https://github.com/yanm1103/War_of_the_Monsters_recomp> (read only; do not copy its game-specific parts: GS state, NGP,
     palettes). The one trick to keep: a root node rotates the game's Z-up into glTF's Y-up. **This game's data is also Z-up,
     facing +y, right handed**, so the same root node works and nothing inside it needs mirroring.
   - Skinning: 2 bones per vertex (weight of bone 0, the rest on bone 1). Skin bone index -> tree node through `sk['skin']`.
   - Animations: `anim.parse_animations(bundle, skeleton_names)` gives sparse keys (`t` in 0..1 of the duration). Sample them
     at 30 fps, or export the keys as they are with `LINEAR` interpolation. **Quaternions are stored inverted: conjugate them.**
     Name each glTF animation with `anim['name']` (the real name from the bundle, e.g. `WALK`, `KOED_FACEUP_IDLE`). The idle is
     `NORMAL_IDLE`. No separate id table is needed: the names come from the game.
   - One texture per monster for now (`bundle.textures()[0]`). Some bundles have more (Jet Jaguar 6, Orga 6, Moguera 5,
     Destoroyah carnival 4): find out which are skins and expose those as costumes; ignore effect textures.
4. **Catalog.** `src/catalog.js` from the `MONSTERS` list in `reference/ste/gen_viewer.py` (key -> display name). Keys that have
   both a low-poly `.cmp` and a high-poly `.bdp` mesh (Godzilla 2000, Ebirah, Moguera, SpaceGodzilla) show them as two costumes
   ("low poly", "high poly"). "Carnival" variants (Destoroyah, Jet Jaguar) are costumes too. Monster logos: the game has HUD
   textures in `hud<name>.bdp`; use them if easy, otherwise show the name (`logo: false`).
5. **Check it for real.** Run the site (`npm run dev`) and screenshot it headless with Edge
   (`msedge --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --screenshot=...`). Do not trust "it loads":
   look at animations whose pose is unmistakable (`KOED_FACEUP_IDLE` lies on its back, `BLOCKHIT_B_DUCK` crouches, `RUN` leans
   forward, `KICK` raises a leg) on at least 3 monsters.
6. **Deploy.** Same workflow as the museum (`master` branch -> Pages). Tell the owner to enable
   Settings -> Pages -> Source: GitHub Actions (only they can).

## Rules

- **The ISO, `GODZILLA.VOL`, `.cmp`/`.bdp` files and any other raw game file never go in the repo** (`.gitignore` covers them).
  Only code and the baked output of step 3.
- Do not mark anything as done before you looked at it rendered. Counting things (animations, names, vertices) proves nothing:
  an earlier mapping of animation names matched every count and was still shifted by five positions.
- Keep the owner informed in short Portuguese messages: what you did, what you saw, what is still missing.

## Open decision for the owner (ask before step 6)

The WotM museum commits its baked `.glb` files in `public/models/` (game-derived content, on public GitHub Pages). This repo is
private for now. Before the site goes public, the owner decides whether to publish the baked models the same way. If they prefer
not to, the alternative is a page that reads the owner's own ISO in the browser (File API) and decodes it in JavaScript, with
nothing from the game on the server; `reference/ste/` is the spec for that port.

## Known gaps in the reference code

- **MechaGodzilla2** is almost all rigid parts (51 of them). The bone of each part is not the submesh index and is not decoded
  yet, so those parts do not follow the animation. Mechagodzilla 3, Megaguirus and Anguirus mix rigid and skinned submeshes: same issue
  for their rigid parts, check them.
- The `.bdp` animations of the Godzilla 2000 are swimming loops (that model is used in the water stages). The fight animations
  are in the `.cmp`.
- Textures other than the first are unused (step 3).
- Scenery (`ControlRoom.bdp`, `water*.bdp`, `objects.bdp`) decodes with the same code (rigid format) but is out of scope.
