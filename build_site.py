"""Build docs/index.html (the public GitHub Pages site) from prototype/allez.html."""
from pathlib import Path

root = Path(__file__).parent
src = (root / "prototype" / "allez.html").read_text(encoding="utf-8")
head, body = src.split("</style>\n", 1)

head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
reset = """<style>
:root { padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }
body { margin: 0; }
img { max-width: 100%; }
[hidden] { display: none !important; }
</style>
"""
page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Allez: what's happening around Lafayette, LA. Music and culture, food, volunteering, and health and wellness.">
<meta name="theme-color" content="#FAF9F6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#061A31" media="(prefers-color-scheme: dark)">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-64.png" type="image/png">
<link rel="apple-touch-icon" href="icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Allez">
<meta property="og:title" content="Allez">
<meta property="og:description" content="What's happening around Lafayette, LA.">
<meta property="og:image" content="icon-512.png">
{reset}{head}</style>
</head>
<body>
{body}</body>
</html>
"""
(root / "docs" / "index.html").write_text(page, encoding="utf-8")
print("wrote docs/index.html")
