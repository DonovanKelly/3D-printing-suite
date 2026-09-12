/** Public API types: geometry uses millimeters and carries each piece's assembly origin. */
export type Settings = {
  width_mm: number;
  height_mm: number;
  base_mm: number;
  relief_mm: number;
  frame: boolean;
  frame_width_mm: number;
  frame_height_mm: number;
  margin_mm: number;
  threshold: number;
  invert: boolean;
  detail: "draft" | "balanced" | "fine";
  min_area_mm2: number;
  layout: "plaque" | "tiles" | "puzzle";
  columns: number;
  rows: number;
  clearance_mm: number;
  bed_width_mm: number;
  bed_height_mm: number;
  hanging: "none" | "loops" | "keyholes";
  background_color: string;
  artwork_color: string;
};
export type Piece = {
  id: string;
  row: number;
  column: number;
  assembly_origin_mm: number[];
  extents_mm: number[];
  material_parts: number;
  volume_mm3: number;
};
export type Manifest = {
  settings: Settings;
  grid: { columns: number; rows: number };
  piece_count: number;
  pieces: Piece[];
  warnings: string[];
};
export type Preview = {
  id: string;
  manifest: Manifest;
  vector_svg: string;
  assembly_svg: string;
  meshes: {
    piece: string;
    material: string;
    origin: number[];
    vertices: number[];
    faces: number[];
  }[];
};
export type View = "relief" | "assembly" | "vector";
export type Update = <K extends keyof Settings>(
  key: K,
  value: Settings[K],
) => void;
