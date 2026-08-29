#!/bin/bash
# Builds GuitarSplit.app into /Applications, so there is one icon to click.
# The app is a thin launcher; all the real code stays in this folder.
#
# /Applications, not ~/Applications: Finder's sidebar shows the former, so an
# app installed in the latter is effectively invisible.
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
APP="/Applications/GuitarSplit.app"
if [ ! -w /Applications ]; then
  APP="$HOME/Applications/GuitarSplit.app"
  echo "note: /Applications is not writable, installing to ~/Applications instead"
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>GuitarSplit</string>
  <key>CFBundleDisplayName</key><string>GuitarSplit</string>
  <key>CFBundleIdentifier</key><string>local.guitarsplit</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>GuitarSplit</string>
  <key>CFBundleIconFile</key><string>GuitarSplit</string>
  <key>LSMinimumSystemVersion</key><string>10.15</string>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/GuitarSplit" <<LAUNCHER
#!/bin/bash
REPO="$REPO"
PORT=8756

# Already running? Reopen the tab instead of starting a second copy.
if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:\$PORT/"; then
  open "http://127.0.0.1:\$PORT/"
  exit 0
fi

if [ ! -x "\$REPO/venv/bin/python" ]; then
  osascript -e 'display alert "GuitarSplit is not set up" message "Open Terminal in the guitar-splitter folder and run ./setup.sh once."'
  exit 1
fi

cd "\$REPO" || exit 1
exec "\$REPO/venv/bin/python" app.py --port "\$PORT"
LAUNCHER
chmod +x "$APP/Contents/MacOS/GuitarSplit"

# Icon: the same red cassette the app itself is built around, drawn with tools
# already on the machine. Kept blunt on purpose - at 16px only the red body,
# the cream label and two reels survive, so those carry the whole shape.
python3 - "$APP" <<'PYICON'
import subprocess, sys, tempfile, pathlib

app = pathlib.Path(sys.argv[1])
svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#1c1715"/><stop offset="1" stop-color="#050404"/></linearGradient>
  <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#e02b21"/><stop offset="55%" stop-color="#a01c15"/>
    <stop offset="1" stop-color="#680f0b"/></linearGradient>
  <linearGradient id="label" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fdfaf3"/><stop offset="1" stop-color="#ddd3c0"/></linearGradient>
</defs>
<rect width="1024" height="1024" rx="228" fill="url(#bg)"/>
<rect x="128" y="258" width="768" height="508" rx="38" fill="url(#body)"/>
<path d="M128 296 q384 -86 768 0 v44 q-384 -74 -768 0z" fill="#ffffff" opacity=".14"/>
<rect x="182" y="312" width="660" height="142" rx="9" fill="url(#label)"/>
<rect x="220" y="356" width="474" height="30" rx="15" fill="#1a1512" opacity=".85"/>
<rect x="220" y="404" width="286" height="20" rx="10" fill="#c9241c" opacity=".8"/>
<circle cx="336" cy="596" r="106" fill="#63100c"/>
<circle cx="336" cy="596" r="62" fill="#141110"/>
<circle cx="336" cy="596" r="62" fill="none" stroke="#efe7d8" stroke-width="17"/>
<circle cx="688" cy="596" r="106" fill="#63100c"/>
<circle cx="688" cy="596" r="62" fill="#141110"/>
<circle cx="688" cy="596" r="62" fill="none" stroke="#efe7d8" stroke-width="17"/>
<rect x="452" y="562" width="120" height="68" rx="12" fill="#2b0705"/>
<rect x="182" y="700" width="660" height="44" rx="7" fill="url(#label)" opacity=".93"/>
<g transform="rotate(-9 806 726)"><rect x="726" y="686" width="164" height="80" rx="7" fill="#6fd44f"/></g>
</svg>"""

# iconutil wants an exact set of names; render each pixel size once and file it
# under every name that needs it.
NAMES = {
    16: ["icon_16x16.png"],
    32: ["icon_32x32.png", "icon_16x16@2x.png"],
    64: ["icon_32x32@2x.png"],
    128: ["icon_128x128.png"],
    256: ["icon_256x256.png", "icon_128x128@2x.png"],
    512: ["icon_512x512.png", "icon_256x256@2x.png"],
    1024: ["icon_512x512@2x.png"],
}

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "i.svg").write_text(svg)
    iconset = d / "GuitarSplit.iconset"
    iconset.mkdir()
    for size, names in NAMES.items():
        subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(d), str(d / "i.svg")],
                       capture_output=True)
        src = d / "i.svg.png"
        if not src.exists():
            print("icon render failed at", size)
            break
        for name in names:
            subprocess.run(["cp", str(src), str(iconset / name)], capture_output=True)
        src.unlink()
    r = subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o",
                        str(app / "Contents/Resources/GuitarSplit.icns")], capture_output=True)
    if r.returncode:
        print("iconutil:", r.stderr.decode()[:200])
PYICON

touch "$APP"
echo "Built $APP"
