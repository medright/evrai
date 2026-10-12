# evrai — splash site

Static one-page site for evrai (applied AI for healthcare operations, by evermed research).
Sibling of [evrsplsh](https://github.com/medright/evrsplsh) and shares its design system
(Manrope, teal/ink glass cards). No build step — edit `index.html`, push to `main`,
GitHub Pages serves it.

Custom domain: add a `CNAME` file containing the domain and configure DNS
(A records for apex → GitHub Pages IPs, CNAME `www` → `medright.github.io`).

## Demos

`demos/<slug>/` holds one watch page per narrated demo: the MP4, a 16:9 poster, English WebVTT
captions, and an `index.html` with the transcript, chapters, `VideoObject`/`Clip` markup and OG tags.
`sitemap.xml` carries the video-sitemap entries. All of it is generated from the narrated demo
assets (recorded on synthetic data by the health-connect e2e suite) and committed:

    python3 tools/build_demos.py --config tools/demos.json --assets <narrated demo dir> --out .

Copy and chapter names live in `tools/demos.json`; styles in `demos/demos.css`. The publishing
standard is health-connect's `docs/VIDEO-PUBLISHING-RUNBOOK.md`.
