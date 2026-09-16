/** Public API types: geometry uses millimeters and carries each piece's assembly origin. */
export type Settings = {
  width_mm: number;
  height_mm: number;
  base_mm: number;
  relief_mm: number;
  shape: "rectangle" | "contour";
  frame: boolean;
  frame_width_mm: number;
  frame_height_mm: number;
  frame_profile: "flat" | "rounded" | "beaded";
  corner_radius_mm: number;
  margin_mm: number;
  crop_to_artwork: boolean;
  threshold: number;
  foreground: "auto" | "dark" | "light";
  invert: boolean;
  detail: "draft" | "balanced" | "fine";
  min_area_mm2: number;
  layout: "plaque" | "tiles" | "puzzle";
  columns: number;
  rows: number;
  split_mode: "size" | "bed";
  piece_size_mm: number;
  puzzle_style: "random" | "regular";
  puzzle_seed: number;
  clearance_mm: number;
  bed_width_mm: number;
  bed_height_mm: number;
  hanging: "none" | "loops" | "keyholes";
  background_color: string;
  artwork_color: string;
  border_material: "artwork" | "background" | "custom";
  border_color: string;
};
export type Piece = {
  id: string;
  row: number;
  column: number;
  assembly_origin_mm: number[];
  separated_origin_mm: number[];
  extents_mm: number[];
  material_parts: number;
  volume_mm3: number;
};
export type Manifest = {
  settings: Settings;
  grid: { columns: number; rows: number };
  piece_count: number;
  plate_count: number;
  separated_extents_mm: number[];
  plates: {
    id: string;
    file: string;
    pieces: { id: string; origin_mm: number[] }[];
  }[];
  pieces: Piece[];
  warnings: string[];
};
export type Preview = {
  id: string;
  manifest: Manifest;
  vector_svg: string;
  assembly_svg: string;
  separated_svg: string;
  meshes: {
    piece: string;
    material: "background" | "artwork" | "border";
    origin: number[];
    vertices: number[];
    faces: number[];
  }[];
};
export type View = "relief" | "pieces" | "assembly" | "vector";
export type Update = <K extends keyof Settings>(
  key: K,
  value: Settings[K],
) => void;
