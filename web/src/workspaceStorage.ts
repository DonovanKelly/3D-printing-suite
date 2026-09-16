/** Optional device-local recovery. One ordered IndexedDB record contains the
 * latest workspace; disabling restore removes artwork as well as the preference.
 * Portable downloads do not depend on browser storage being available. */
import { validateRecovery, type Workspace } from "./workspace";
import type { Settings } from "./types";

let database: Promise<IDBDatabase> | undefined;
function openDatabase() {
  return database ??= new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open("3d-printing-suite-workspaces", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("recovery");
    request.onsuccess = () => {
      const db = request.result;
      db.onversionchange = () => { db.close(); database = undefined; };
      resolve(db);
    };
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(Error("Browser storage is blocked by another tab."));
  }).catch((error) => { database = undefined; throw error; });
}

async function transaction(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest) {
  const db = await openDatabase();
  return new Promise<unknown>((resolve, reject) => {
    const tx = db.transaction("recovery", mode);
    const request = action(tx.objectStore("recovery"));
    tx.oncomplete = () => resolve(request.result);
    tx.onabort = () => reject(tx.error || Error("Browser storage was interrupted."));
    tx.onerror = () => reject(tx.error || Error("Browser storage is unavailable."));
  });
}

export async function readRecovery(defaults: Settings) {
  const value = await transaction("readonly", (store) => store.get("last"));
  return value === undefined ? null : validateRecovery(value, defaults);
}

export async function writeRecovery(workspace: Workspace | null) {
  await transaction("readwrite", (store) => workspace
    ? store.put({ ...workspace, name: workspace.name.trim() || "Untitled project", version: 1 }, "last")
    : store.delete("last"));
}
