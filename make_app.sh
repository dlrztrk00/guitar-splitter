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

# Icon, drawn with tools already on the machine.
python3 - "$APP" <<'PYICON'
import subprocess, sys, tempfile, pathlib
app = pathlib.Path(sys.argv[1])
svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024">
<rect width="1024" height="1024" rx="230" fill="#1b1817"/>
<g stroke="#e0813f" stroke-width="30" stroke-linecap="round" fill="none">
<path d="M250 300 L774 300"/><path d="M250 430 L774 430"/>
<path d="M250 560 L774 560" stroke="#4a423e"/><path d="M250 690 L774 690" stroke="#4a423e"/>
</g><circle cx="390" cy="365" r="70" fill="#e0813f"/></svg>'''
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "i.svg").write_text(svg)
    iconset = d / "GuitarSplit.iconset"; iconset.mkdir()
    for size in (32, 64, 128, 256, 512, 1024):
        subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(d), str(d / "i.svg")],
                       capture_output=True)
        src = d / "i.svg.png"
        if not src.exists():
            break
        for name in (f"icon_{size}x{size}.png", f"icon_{size//2}x{size//2}@2x.png"):
            subprocess.run(["cp", str(src), str(iconset / name)], capture_output=True)
        src.unlink()
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o",
                    str(app / "Contents/Resources/GuitarSplit.icns")], capture_output=True)
PYICON

touch "$APP"
echo "Built $APP"
