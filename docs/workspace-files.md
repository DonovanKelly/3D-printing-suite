# Workspace files

Edit the project name above the preview to name your work. Workspace files,
3MF downloads, print-pack ZIPs, and individual plate downloads use that name.
Characters that cannot appear in filenames become hyphens. The imported source
file is never renamed or overwritten. A custom project name stays in place when
you replace its artwork.

**Save workspace** (Ctrl/Cmd+S) downloads a `.print-workspace` file containing:

- The original image or SVG bytes, including the bundled artwork for a sample.
- Every geometry, image-selection, printer, layout, seed, and color setting.
- The project name and selected Relief, Pieces, Assembly, or Vector tab.

Finish a numeric edit with Enter or by leaving the field before saving. A
workspace may contain unfinished settings that do not currently generate valid
geometry; save it, reopen it, and continue correcting the settings. Print
downloads still require a valid, current preview.

Use **Open workspace** to reopen the file in the app, including in a new browser
tab or on another device. The preview is rebuilt from the saved source and
settings. Opening a workspace asks before replacing changes that have not been
saved to a file. Cancel leaves the current work open. Unreadable files,
unsupported versions, and malformed metadata also leave current work intact.
Files download through your browser; subsequent saves create another download
and do not overwrite a selected disk file in place. Operating-system file
association/double-click launching is not configured.

## Restore when returning

Enable **Restore on return** to keep the latest workspace in this browser's
IndexedDB storage. The app saves committed edits, the original artwork, the
project name, and the selected preview tab. When you reload or reopen the same
app address, it restores that workspace automatically. This is optional and is
off until enabled. Turning it off removes the stored workspace.

The status beside the option confirms when the browser write completes. A
failed write is shown explicitly; you can still download a workspace file.
Browser recovery stores one latest workspace for this app address and browser
profile. Multiple tabs share that record; the most recently edited tab wins.
Use workspace files to keep several designs or transfer them between devices.
Clearing site data, private browsing, or browser storage eviction can remove
recovery data. Keep a downloaded workspace for a durable copy.

Artwork and settings stay on the client device. No upload, account, or server
storage is involved. Offline opening works after the app's assets have been
cached from a first visit. Camera orbit/zoom, open inspector sections, generated
meshes, and old print download links are not stored.

## Format and validation

Version 2 is UTF-8 JSON with format `3d-printing-suite-workspace`, `version: 2`,
`name`, `settings`, `view`, and `artwork`. Artwork stores `name`, `type`, and
`base64` source bytes, with no filesystem paths or external image references.
The reader bounds the document to 17 MiB and decoded artwork to 12 MiB, validates
required setting types/enums/colors and metadata, and rejects unknown versions.
Version 1 files and browser recovery records remain readable: missing border
settings migrate to `border_material: "artwork"` and the default third-color
swatch. Version 2 saves `border_material` and `border_color` and requires both.
The version increase prevents older app builds from silently losing an independent
border material when reopening a newer document.
Rust remains responsible for image decoding, resource limits, geometry settings
constraints, and printability checks. Invalid image bytes or impossible geometry
produce the normal editable preview error after opening.

The browser recovery record stores a structured-cloned File and versioned
metadata in a single transaction; it does not encode artwork on each edit.
Opening a document replaces the source and settings together and invalidates
previous print exports. A name or preview-tab edit does not rebuild geometry.
Workspace save/open is independent of service-worker asset caching and remains
available when IndexedDB is blocked or full.
