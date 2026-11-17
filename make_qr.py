"""Make a printable QR code for the app's public link, in Allez navy.

Usage: python3 make_qr.py https://johnnycrahat-max.github.io/allez/
Writes docs/qr-code.png and docs/qr-code.svg.
"""
import sys
import segno

url = sys.argv[1]
qr = segno.make(url, error="h")
qr.save("docs/qr-code.png", scale=16, border=4, dark="#092B51", light="#FFFFFF")
qr.save("docs/qr-code.svg", scale=16, border=4, dark="#092B51", light="#FFFFFF")
print("QR code for", url)
