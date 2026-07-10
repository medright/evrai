# evrai — splash site

Static one-page site for evrai (applied AI for healthcare operations, by evermed research).
Sibling of [evrsplsh](https://github.com/medright/evrsplsh) and shares its design system
(Manrope, teal/ink glass cards). No build step — edit `index.html`, push to `main`,
GitHub Pages serves it.

Custom domain: add a `CNAME` file containing the domain and configure DNS
(A records for apex → GitHub Pages IPs, CNAME `www` → `medright.github.io`).
