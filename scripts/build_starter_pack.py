"""Build a portable sample gallery and print packs from the checked-in example settings."""

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from relief_studio.cli import sample_bytes
from relief_studio.exports import export_project
from relief_studio.geometry import build_project
from relief_studio.settings import Settings

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="New output directory; existing folders are preserved"
    )
    destination = parser.parse_args().output
    destination.mkdir(parents=True, exist_ok=False)
    cards = []
    examples = [
        ("plaque", "Framed relief", "180 × 180 mm · Start here", {}),
        (
            "wall-puzzle",
            "Interlocking wall art",
            "540 × 540 mm · Automatic puzzle split + top loops",
            {},
        ),
        ("wall-tiles", "Large rectangular panels", "540 × 360 mm · Fewer, larger pieces", {}),
        (
            "rear-keyholes",
            "Hidden hanging recesses",
            "180 × 180 mm · 5 mm backing · Experimental",
            {},
        ),
        *(
            (
                "fit-pair",
                f"Fit pair · {gap:.2f} mm",
                "80 × 40 mm · Compare before printing the wall art",
                {"clearance_mm": gap},
            )
            for gap in (0.15, 0.25, 0.35)
        ),
    ]
    data = sample_bytes()
    for example, title, subtitle, overrides in examples:
        config = json.loads((EXAMPLES / f"{example}.json").read_text()) | overrides
        settings = Settings(**config)
        slug = example + (f"-{round(overrides['clearance_mm'] * 100):02d}" if overrides else "")
        manifest = export_project(build_project(data, settings), destination / slug, data)
        print(f"{slug}: {manifest['piece_count']} pieces")
        cards.append(
            f'<article><a href="{slug}/preview.png"><img src="{slug}/preview.png" '
            f'alt="{title}"/></a><h2>{title}</h2><p>{subtitle}</p>'
            f"<p>{manifest['piece_count']} pieces · two material parts where artwork is present</p>"
            f'<a class="button" href="{slug}/print-pack.zip">Download print pack</a> '
            f'<a href="{slug}/PRINTING.md">Print instructions</a></article>'
        )
    (destination / "alpine.svg").write_bytes(data)
    (destination / "index.html").write_text(
        """<!doctype html>
<html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relief Studio · Starter collection</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f4f0;color:#252b28;
font:15px/1.6 system-ui,sans-serif}
main{max-width:1240px;padding:48px 24px;margin:auto}
h1{font-size:38px;line-height:1.2;margin:0 0 12px}
h2{font-size:22px;margin:16px 0 8px}p{margin:8px 0 18px;color:#626b62}a{color:#285f49}
.intro{max-width:740px;margin-bottom:40px}.gallery{display:grid;
grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:32px}
article{border-top:1px solid #cbd2c7;padding-top:24px}
img{width:100%;height:280px;object-fit:contain}
.button{display:inline-block;padding:8px 12px;margin:5px 12px 5px 0;
border:1px solid #285f49;border-radius:5px;text-decoration:none}
footer{border-top:1px solid #cbd2c7;margin-top:48px;padding-top:24px;font-size:13px}
</style><main><h1>Relief Studio</h1><div class="intro">
<p>Your first collection of two-color printable wall art.</p>
<p>Open a pack, read PRINTING.md, and import its grouped 3MF pieces in Bambu Studio.
Choose the actual AMS slots for Background and Artwork + frame. Try the small fit
pairs before committing to a large puzzle. These are generated meshes, not physical print tests.</p>
<p>This gallery works directly from a folder on your computer.
<a href="alpine.svg">Original sample artwork</a></p></div>
<div class="gallery">"""
        + "".join(cards)
        + """</div><footer>
All dimensions are millimeters. PLA/P1S starting examples, with a 230 mm usable footprint per piece.
Brims, prime towers, tiny details, and hanging features still need slicer inspection.
Puzzle joints are alignment features; support each wall panel.
Rear keyholes and loops are not load-rated.
Settings, assembly labels, closed-mesh checks, and source hashes are included in each pack.
</footer></main></html>"""
    )
    with ZipFile(destination / "starter-collection.zip", "w", ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file() and path.name != "starter-collection.zip":
                archive.write(path, path.relative_to(destination))
    print(f"Open {destination.resolve() / 'index.html'}")


if __name__ == "__main__":
    main()
