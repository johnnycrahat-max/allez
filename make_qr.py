"""Make a printable QR code for the app's public link.

Usage: python3 make_qr.py https://your-name.github.io/ca-se-passe/
Writes docs/qr-code.png and docs/qr-code.svg.
"""
import sys
import segno

url = sys.argv[1]
qr = segno.make(url, error="h")
qr.save("docs/qr-code.png", scale=16, border=4, dark="#15201B")
qr.save("docs/qr-code.svg", scale=16, border=4, dark="#15201B")
print("QR code for", url)
