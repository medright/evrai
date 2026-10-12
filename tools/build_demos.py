#!/usr/bin/env python3
"""Build evrai.online demo watch pages from narrated demo assets.

Usage: python3 tools/build_demos.py --config tools/demos.json --assets <narrated demo dir> --out .

For each demo, finds in --assets (by the manifest outputBasename):
  *<base>*web*.mp4 (falls back to any *<base>*.mp4), *<base>*.jpg poster,
  *<base>*.vtt captions, *<base>*-timeline.json narration timeline, and
  *<base>*-transcript.txt (a title line, then one readable paragraph per narration segment).
Writes demos/<slug>/{index.html,<slug>.mp4,poster.jpg,captions.en.vtt},
demos/index.html and sitemap.xml. demos/demos.css is hand-edited. The output is static and
committed; the site itself has no build step. Re-run after re-recording a demo.
"""
import argparse
import glob
import html
import json
import os
import shutil
import subprocess
import sys

DISCLOSURE = (
    "This recording runs on a local demo stack with synthetic patients, "
    "users and facilities. It is not a live customer deployment and shows no protected "
    "health information. The narration is a synthetic, computer-generated voice."
)


def find(assets, base, pattern, prefer=None):
    hits = sorted(glob.glob(os.path.join(assets, f"*{base}*{pattern}")))
    if prefer:
        preferred = [h for h in hits if prefer in os.path.basename(h)]
        if preferred:
            return preferred[0]
    if not hits:
        sys.exit(f"missing {pattern} for {base} in {assets}")
    return hits[0]


def probe_seconds(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def iso_duration(seconds):
    s = int(round(seconds))
    return f"PT{s // 60}M{s % 60}S"


def clock(seconds):
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def esc(text):
    return html.escape(text, quote=True)


def header(depth_prefix, current):
    return f"""  <div class="wrap">
    <header>
      <a class="brand" href="/">
        <img src="/logo.svg" alt="evrai logo" width="36" height="36">
        <span>
          <span class="kicker">evermed research</span>
          <span class="name">evr<em>ai</em></span>
        </span>
      </a>
      <nav aria-label="Primary">
        <a href="/#agents">Agents</a>
        <a href="/demos/"{' aria-current="page"' if current == 'library' else ''}>Demos</a>
        <a href="/#products">Products</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>"""


FOOTER = """    <footer>
      <span>© 2026 · evrai</span>
      <span><a href="https://www.evermedresearch.org/privacy.html">Privacy</a></span>
    </footer>
  </div>"""

HEAD_COMMON = """  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="/logo.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/demos/demos.css">
  <meta name="theme-color" content="#0f172a">"""

# Seeks the player for ?t=NN deep links and chapter buttons (never autoplays on load), and
# carries any utm_* parameters into the walkthrough email so the inquiry keeps its campaign.
PAGE_SCRIPT = """  <script>
  (function () {
    var video = document.getElementById('demo-video');
    var params = new URLSearchParams(window.location.search);
    function seek(t, play) {
      if (!video || !(t >= 0)) return;
      var apply = function () { video.currentTime = t; if (play) video.play().catch(function () {}); };
      if (video.readyState >= 1) apply(); else video.addEventListener('loadedmetadata', apply, { once: true });
    }
    var start = parseFloat(params.get('t'));
    if (start >= 0) { seek(start, false); }
    document.querySelectorAll('[data-t]').forEach(function (el) {
      el.addEventListener('click', function (event) {
        event.preventDefault();
        seek(parseFloat(el.getAttribute('data-t')), true);
        if (video) video.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    });
    var utm = [];
    params.forEach(function (value, key) { if (/^utm_[a-z]+$/.test(key)) utm.push(key + '=' + value); });
    if (utm.length) {
      document.querySelectorAll('a[data-cta]').forEach(function (a) {
        a.href += '&body=' + encodeURIComponent('\\n\\n(' + window.location.pathname + ' ' + utm.join(' ') + ')');
      });
    }
  })();
  </script>"""


def watch_page(cfg, demo, meta, others):
    site = cfg["site"]
    url = f"{site}/demos/{demo['slug']}/"
    video_url = f"{url}{demo['slug']}.mp4"
    poster_url = f"{url}poster.jpg"
    chapters = meta["chapters"]
    clips = [
        {
            "@type": "Clip",
            "name": c["name"],
            "startOffset": int(c["start"]),
            "endOffset": int(c["end"]),
            "url": f"{url}?t={int(c['start'])}",
        }
        for c in chapters
    ]
    ld = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": demo["h1"],
        "description": demo["description"],
        "thumbnailUrl": [poster_url],
        "uploadDate": cfg["uploadDate"],
        "duration": iso_duration(meta["duration"]),
        "contentUrl": video_url,
        "inLanguage": "en",
        "publisher": {"@type": "Organization", "name": "evrai", "url": f"{site}/"},
        "hasPart": clips,
    }
    chapter_items = "\n".join(
        f'          <li><a href="?t={int(c["start"])}" data-t="{int(c["start"])}">'
        f'<span class="ts">{clock(c["start"])}</span> {esc(c["name"])}</a></li>'
        for c in chapters
    )
    transcript = "\n".join(
        f'        <p><a class="ts" href="?t={int(s["start"])}" data-t="{int(s["start"])}">{clock(s["start"])}</a> '
        f"{esc(s['text'])}</p>"
        for s in meta["segments"]
    )
    points = "\n".join(f"          <li>{esc(p)}</li>" for p in demo["points"])
    extra = (
        f'\n        <p><strong>{esc(demo.get("extra_label", "Note."))}</strong> {esc(demo["extra_disclosure"])}</p>'
        if demo.get("extra_disclosure")
        else ""
    )
    related = "\n".join(
        f'        <a class="related" href="/demos/{o["slug"]}/"><span class="tag">{esc(o["eyebrow"])}</span>'
        f'<strong>{esc(o["card_title"])}</strong><span>{esc(o["card_blurb"])}</span></a>'
        for o in others
    )
    subject = esc(demo["cta_subject"].replace(" ", "%20"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{HEAD_COMMON}
  <title>{esc(demo['title'])}</title>
  <meta name="description" content="{esc(demo['description'])}">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="video.other">
  <meta property="og:title" content="{esc(demo['h1'])}">
  <meta property="og:description" content="{esc(demo['description'])}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{poster_url}">
  <meta property="og:image:width" content="{meta['poster_w']}">
  <meta property="og:image:height" content="{meta['poster_h']}">
  <meta property="og:video" content="{video_url}">
  <meta property="og:video:type" content="video/mp4">
  <meta property="og:video:width" content="{meta['w']}">
  <meta property="og:video:height" content="{meta['h']}">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">
{json.dumps(ld, indent=2)}
  </script>
</head>
<body>
{header('', 'watch')}

    <main>
      <p class="crumbs"><a href="/">Home</a> / <a href="/demos/">Demos</a> / {esc(demo['card_title'])}</p>
      <div class="watch-head">
        <span class="eyebrow">{esc(demo['eyebrow'])}</span>
        <h1>{esc(demo['h1'])}</h1>
        <p class="lede">{esc(demo['intro'])}</p>
      </div>

      <div class="player">
        <video id="demo-video" controls preload="metadata" playsinline poster="player.jpg" width="{meta['w']}" height="{meta['h']}">
          <source src="{demo['slug']}.mp4" type="video/mp4">
          <track kind="captions" src="captions.en.vtt" srclang="en" label="English" default>
          Your browser can't play this video. <a href="{demo['slug']}.mp4">Download the MP4</a>.
        </video>
        <p class="meta">Narrated walkthrough · {clock(meta['duration'])} · English captions · synthetic demo data</p>
      </div>

      <aside class="disclosure" aria-label="About this recording">
        <p><strong>Demo data.</strong> {esc(demo.get("disclosure", DISCLOSURE))}</p>{extra}
      </aside>

      <div class="watch-grid">
        <section class="card" aria-labelledby="see">
          <h2 id="see">What you'll see</h2>
          <ul class="points">
{points}
          </ul>
        </section>
        <section class="card" aria-labelledby="chapters">
          <h2 id="chapters">Chapters</h2>
          <ol class="chapters">
{chapter_items}
          </ol>
        </section>
      </div>

      <section class="card transcript" aria-labelledby="transcript">
        <h2 id="transcript">Transcript</h2>
{transcript}
      </section>

      <section class="contact">
        <h2>Want to see this on your workflow?</h2>
        <p>We run walkthroughs against realistic synthetic populations that match your case mix.</p>
        <a class="btn btn-primary" data-cta href="mailto:evr@evrai.online?subject={subject}">Request a walkthrough</a>
      </section>

      <section aria-labelledby="more">
        <h2 id="more" class="more-head">More demos</h2>
        <div class="related-grid">
{related}
        </div>
      </section>
    </main>

{FOOTER}
{PAGE_SCRIPT}
</body>
</html>
"""


def library_page(cfg, demos, metas):
    site = cfg["site"]
    cards = "\n".join(
        f"""        <a class="demo-card" href="/demos/{d['slug']}/">
          <img src="/demos/{d['slug']}/player.jpg" alt="" width="{metas[d['slug']]['w']}" height="{metas[d['slug']]['h']}" loading="lazy">
          <span class="body">
            <span class="tag">{esc(d['eyebrow'])}</span>
            <strong>{esc(d['card_title'])}</strong>
            <span class="blurb">{esc(d['card_blurb'])}</span>
            <span class="watch">Watch · {clock(metas[d['slug']]['duration'])}</span>
          </span>
        </a>"""
        for d in demos
    )
    ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "evrai demos",
        "url": f"{site}/demos/",
        "hasPart": [{"@type": "VideoObject", "name": d["h1"], "url": f"{site}/demos/{d['slug']}/"} for d in demos],
    }
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{HEAD_COMMON}
  <title>Demos | evrai — Applied AI for Healthcare Operations</title>
  <meta name="description" content="Narrated walkthroughs of Health-Connect and evrai workflows, recorded on synthetic demo data, each with captions, chapters and a transcript.">
  <link rel="canonical" href="{site}/demos/">
  <meta property="og:type" content="website">
  <meta property="og:title" content="evrai demos">
  <meta property="og:description" content="Narrated walkthroughs recorded on synthetic demo data.">
  <meta property="og:url" content="{site}/demos/">
  <meta property="og:image" content="{site}/demos/{demos[0]['slug']}/poster.jpg">
  <script type="application/ld+json">
{json.dumps(ld, indent=2)}
  </script>
</head>
<body>
{header('', 'library')}

    <main>
      <div class="watch-head">
        <span class="eyebrow">Demos</span>
        <h1>See the workflows, end to end.</h1>
        <p class="lede">Short narrated walkthroughs recorded on a local demo stack with synthetic patients, users and facilities. Each has captions, chapters and a full transcript.</p>
      </div>
      <div class="demo-grid">
{cards}
      </div>
      <aside class="disclosure" aria-label="About these recordings">
        <p><strong>Demo data.</strong> {esc(DISCLOSURE)}</p>
      </aside>
    </main>

{FOOTER}
</body>
</html>
"""


def sitemap(cfg, demos, metas):
    site = cfg["site"]
    urls = [f"  <url>\n    <loc>{site}/</loc>\n  </url>", f"  <url>\n    <loc>{site}/demos/</loc>\n  </url>"]
    for d in demos:
        m = metas[d["slug"]]
        page = f"{site}/demos/{d['slug']}/"
        urls.append(
            f"""  <url>
    <loc>{page}</loc>
    <video:video>
      <video:thumbnail_loc>{page}poster.jpg</video:thumbnail_loc>
      <video:title>{esc(d['h1'])}</video:title>
      <video:description>{esc(d['description'])}</video:description>
      <video:content_loc>{page}{d['slug']}.mp4</video:content_loc>
      <video:duration>{int(round(m['duration']))}</video:duration>
      <video:publication_date>{cfg['uploadDate']}T12:00:00+00:00</video:publication_date>
      <video:family_friendly>yes</video:family_friendly>
    </video:video>
  </url>"""
        )
    body = "\n".join(urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
{body}
</urlset>
"""


def image_size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    w, h = out.split("x")[:2]
    return int(w), int(h)


def player_poster(m, dest):
    """The 16:9 poster (for OG cards and the sitemap) pillarboxes the 16:10 video; crop the bars off for the player."""
    content_w = round(m["poster_h"] * m["w"] / m["h"] / 2) * 2
    x = (m["poster_w"] - content_w) // 2
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", m["poster"], "-vf",
         f"crop={content_w}:{m['poster_h']}:{x}:0,scale={m['w']}:{m['h']}", "-q:v", "3", dest],
        check=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--assets", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    # "published": false keeps a demo's copy in the config while its recording is still in review.
    demos = [d for d in cfg["demos"] if d.get("published", True)]
    metas = {}
    for d in demos:
        base = d["base"]
        mp4 = find(args.assets, base, ".mp4", prefer="web")
        poster = find(args.assets, base, ".jpg")
        vtt = find(args.assets, base, ".vtt")
        timeline = json.load(open(find(args.assets, base, "-timeline.json")))
        paragraphs = [p.strip() for p in open(find(args.assets, base, "-transcript.txt")).read().split("\n\n") if p.strip()]
        duration = probe_seconds(mp4)
        w, h = image_size(mp4)
        pw, ph = image_size(poster)
        segs = timeline["segments"]
        texts = paragraphs[1:]  # drop the title line
        if len(texts) != len(segs):
            sys.exit(f"{base}: {len(texts)} transcript paragraphs for {len(segs)} segments")
        missing = [s["id"] for s in segs if s["id"] not in d["chapters"]]
        if missing:
            sys.exit(f"{base}: no chapter name for segments {missing}")
        chapters, segments = [], []
        for i, s in enumerate(segs):
            # A chapter starts where its narration starts (lead-in pause included for the first one).
            start = 0.0 if i == 0 else s["startsAtMs"] / 1000.0
            end = segs[i + 1]["startsAtMs"] / 1000.0 if i + 1 < len(segs) else duration
            chapters.append({"name": d["chapters"][s["id"]], "start": start, "end": end})
            segments.append({"start": s["startsAtMs"] / 1000.0, "text": " ".join(texts[i].split())})
        metas[d["slug"]] = {
            "duration": duration, "w": w, "h": h, "poster_w": pw, "poster_h": ph,
            "chapters": chapters, "segments": segments, "mp4": mp4, "poster": poster, "vtt": vtt,
        }
    demos_dir = os.path.join(args.out, "demos")
    os.makedirs(demos_dir, exist_ok=True)
    for d in demos:
        m = metas[d["slug"]]
        page_dir = os.path.join(demos_dir, d["slug"])
        os.makedirs(page_dir, exist_ok=True)
        shutil.copyfile(m["mp4"], os.path.join(page_dir, f"{d['slug']}.mp4"))
        shutil.copyfile(m["poster"], os.path.join(page_dir, "poster.jpg"))
        player_poster(m, os.path.join(page_dir, "player.jpg"))
        shutil.copyfile(m["vtt"], os.path.join(page_dir, "captions.en.vtt"))
        others = [o for o in demos if o["slug"] != d["slug"]]
        with open(os.path.join(page_dir, "index.html"), "w") as f:
            f.write(watch_page(cfg, d, m, others))
    with open(os.path.join(demos_dir, "index.html"), "w") as f:
        f.write(library_page(cfg, demos, metas))
    with open(os.path.join(args.out, "sitemap.xml"), "w") as f:
        f.write(sitemap(cfg, demos, metas))
    for d in demos:
        m = metas[d["slug"]]
        print(f"{d['slug']}: {clock(m['duration'])} {m['w']}x{m['h']} "
              f"{os.path.getsize(m['mp4']) / 1e6:.1f} MB, {len(m['chapters'])} chapters")


if __name__ == "__main__":
    main()
