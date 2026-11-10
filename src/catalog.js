// What the site shows. Each exported costume is public/models/<PREFIX><costume>.glb (mesh, skeleton, idle and the list of
// animations); the animations are public/models/<PREFIX>/aNNN.glb (<PREFIX>_<n>/ for a costume with animations of its own),
// one per file (tools/export_glb.py). The list is the order of the game's character select.
// labels: costume names in the costume select (default "costume N"; hidden when there is only one).
// zoom: camera dolly per monster (wide wings or tails make the framing box wide).
// logo: false when there is no public/logos/<prefix>.png: the monster list shows the name instead.
export const MONSTERS = [
  { prefix: "GODZILLA2K", name: "Godzilla 2000", costumes: [0, 1], labels: ["low poly", "high poly"], logo: false },
  { prefix: "GODZILLA90S", name: "Godzilla 90s", costumes: [0], logo: false },
  { prefix: "MECHAGODZILLA2", name: "Mechagodzilla 2", costumes: [0], logo: false },
  { prefix: "MECHAGODZILLA3", name: "Mechagodzilla 3", costumes: [0], logo: false },
  { prefix: "SPACEGODZILLA", name: "SpaceGodzilla", costumes: [0, 1], labels: ["default", "rail stage"], logo: false },
  { prefix: "ANGUIRUS", name: "Anguirus", costumes: [0], logo: false },
  { prefix: "BARAGON", name: "Baragon", costumes: [0], logo: false },
  { prefix: "BIOLLANTE", name: "Biollante", costumes: [0], logo: false },
  { prefix: "DESTOROYAH", name: "Destoroyah", costumes: [0, 1], labels: ["default", "carnival"], logo: false },
  { prefix: "EBIRAH", name: "Ebirah", costumes: [0, 1], zoom: 1.5, labels: ["default", "rail stage"], logo: false },
  { prefix: "GHIDORAH", name: "King Ghidorah", costumes: [0], logo: false },
  { prefix: "MGHIDORAH", name: "Mecha-King Ghidorah", costumes: [0], logo: false },
  { prefix: "GIGAN", name: "Gigan", costumes: [0], logo: false },
  { prefix: "JETJAGUAR", name: "Jet Jaguar", costumes: [0, 1], labels: ["default", "carnival"], logo: false },
  { prefix: "MEGAGUIRUS", name: "Megaguirus", costumes: [0], zoom: 1.2, logo: false },
  { prefix: "MEGALON", name: "Megalon", costumes: [0], logo: false },
  { prefix: "MOGUERA", name: "Moguera", costumes: [0, 1], labels: ["low poly", "high poly"], logo: false },
  { prefix: "MOTHRA", name: "Mothra", costumes: [0], logo: false },
  { prefix: "MOTHRALARVAE", name: "Mothra (larva)", costumes: [0], zoom: 1.3, logo: false },
  { prefix: "ORGA", name: "Orga", costumes: [0], logo: false },
  { prefix: "RODAN", name: "Rodan", costumes: [0], zoom: 1.3, logo: false },
];
