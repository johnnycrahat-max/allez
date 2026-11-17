"""Build docs/index.html (a standalone web page) from prototype/ca-se-passe.html."""
from pathlib import Path

root = Path(__file__).parent
src = (root / "prototype" / "ca-se-passe.html").read_text(encoding="utf-8")
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
<meta name="description" content="What's happening around Lafayette, LA: music and culture, food, volunteering, and health and wellness.">
<meta name="theme-color" content="#F2F5F2">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="icon.svg">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Ça Se Passe">
{reset}{head}</style>
</head>
<body>
{body}</body>
</html>
"""
(root / "docs" / "index.html").write_text(page, encoding="utf-8")
print("wrote docs/index.html")
