/** Portable workspace documents embed source bytes, never meshes or local paths.
 * Validate the complete envelope before replacing an open project. Geometry
 * constraints stay in Rust so even an unfinished design can be saved and repaired.
 * Version 1 documents migrate missing border settings to the original artwork material. */
import sample from "../../src/relief_studio/assets/alpine.svg?raw";
import type { Settings, View } from "./types";

export const WORKSPACE_EXTENSION = ".print-workspace";
export const MAX_ARTWORK_BYTES = 12 * 1024 * 1024;
const MAX_DOCUMENT_BYTES = 17 * 1024 * 1024;
export type Workspace = {
  name: string;
  settings: Settings;
  view: View;
  file: File | null;
};
const choices: Partial<Record<keyof Settings, readonly string[]>> = {
  shape: ["rectangle", "contour"],
  frame_profile: ["flat", "rounded", "beaded"],
  foreground: ["auto", "dark", "light"],
  detail: ["draft", "balanced", "fine"],
  layout: ["plaque", "tiles", "puzzle"],
  split_mode: ["size", "bed"],
  puzzle_style: ["random", "regular"],
  hanging: ["none", "loops", "keyholes"],
  border_material: ["artwork", "background", "custom"],
};
const views: readonly string[] = ["relief", "pieces", "assembly", "vector"];

export function projectName(value: string) {
  return value.trim().slice(0, 120) || "Untitled project";
}

export function fileStem(value: string) {
  const clean = projectName(value)
    .replace(/[<>:"/\\|?*\u0000-\u001f\u007f]/g, "-")
    .replace(/^[. ]+|[. ]+$/g, "");
  return !clean || /^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)/i.test(clean)
    ? `project-${clean || "untitled"}` : clean;
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw Error("This workspace is incomplete or damaged.");
  return value as Record<string, unknown>;
}

function metadata(value: unknown, defaults: Settings) {
  const data = record(value);
  if (typeof data.name !== "string" || !data.name.trim() || data.name.length > 120)
    throw Error("The workspace needs a project name of 1–120 characters.");
  if (typeof data.view !== "string" || !views.includes(data.view))
    throw Error("The workspace contains an unknown preview tab.");
  const settings = record(data.settings);
  const validated = { ...defaults };
  for (const key of Object.keys(defaults) as (keyof Settings)[]) {
    const legacyBorder = data.version === 1 && (key === "border_material" || key === "border_color");
    const value = legacyBorder && settings[key] === undefined ? defaults[key] : settings[key];
    if (typeof value !== typeof defaults[key] ||
      (typeof value === "number" && !Number.isFinite(value)) ||
      (choices[key] && !choices[key]!.includes(value as string)) ||
      (key.endsWith("_color") && !/^#[0-9a-f]{6}$/i.test(String(value))))
      throw Error(`The workspace contains an invalid ${key} setting.`);
    Object.assign(validated, { [key]: value });
  }
  return { name: projectName(data.name), view: data.view as View, settings: validated };
}

export async function serializeWorkspace(workspace: Workspace) {
  const file = workspace.file ?? new File([sample], "alpine.svg", { type: "image/svg+xml" });
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 32768)
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  return JSON.stringify({
    format: "3d-printing-suite-workspace",
    version: 2,
    name: projectName(workspace.name),
    settings: workspace.settings,
    view: workspace.view,
    artwork: { name: file.name, type: file.type, base64: btoa(binary) },
  });
}

export async function parseWorkspace(file: File, defaults: Settings): Promise<Workspace> {
  if (file.size > MAX_DOCUMENT_BYTES) throw Error("Choose a workspace smaller than 17 MiB.");
  let value: unknown;
  try { value = JSON.parse(await file.text()); }
  catch { throw Error("This file is not a readable workspace. Choose a .print-workspace file."); }
  const data = record(value);
  if (data.format !== "3d-printing-suite-workspace")
    throw Error("This is not a workspace file. Use Upload artwork for images.");
  if (data.version !== 1 && data.version !== 2)
    throw Error("This workspace version is not supported. Open it in the app version that saved it.");
  const project = metadata(data, defaults);
  const artwork = record(data.artwork);
  if (typeof artwork.name !== "string" || !artwork.name || artwork.name.length > 255 ||
    typeof artwork.type !== "string" || artwork.type.length > 100 ||
    typeof artwork.base64 !== "string" || !artwork.base64.length ||
    artwork.base64.length > 4 * Math.ceil(MAX_ARTWORK_BYTES / 3) ||
    artwork.base64.length % 4 !== 0 ||
    !/^[A-Za-z0-9+/]*={0,2}$/.test(artwork.base64))
    throw Error("The workspace artwork is missing, damaged, or larger than 12 MiB.");
  let bytes: Uint8Array<ArrayBuffer>;
  try { bytes = Uint8Array.from(atob(artwork.base64), (character) => character.charCodeAt(0)); }
  catch { throw Error("The workspace artwork is damaged."); }
  return { ...project, file: new File([bytes], artwork.name, { type: artwork.type }) };
}

export function validateRecovery(value: unknown, defaults: Settings): Workspace {
  const data = record(value);
  if (data.version !== 1 && data.version !== 2) throw Error("Unsupported browser workspace version.");
  const project = metadata(data, defaults);
  if (data.file !== null && (!(data.file instanceof File) || data.file.size > MAX_ARTWORK_BYTES))
    throw Error("The browser's saved artwork could not be read.");
  return { ...project, file: data.file as File | null };
}

export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  // Keep the URL alive long enough for the browser to take ownership of the download.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
