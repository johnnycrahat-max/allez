# Ça Se Passe Lafayette

A phone-friendly app showing what's happening around Lafayette, LA, sorted into four categories:
Music & Culture, Food, Volunteer, and Health & Wellness.

This is a clickable prototype that uses real listings gathered on Nov 16, 2026. Automatic updates
from each venue's website are the next step.

## Files

- `docs/` is the public website that GitHub Pages serves.
- `prototype/ca-se-passe.html` is the source page. After editing it, run `python3 build_site.py`
  to rebuild `docs/index.html`.
- `make_qr.py` makes a QR code for the public link: `python3 make_qr.py <url>`. It writes
  `docs/qr-code.png` and `docs/qr-code.svg`.

## Publishing with GitHub Pages

1. In the repository on GitHub, open **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Pick the **main** branch and the **/docs** folder, then **Save**.
4. After a minute the app is live at `https://<your-username>.github.io/<repo-name>/`.
