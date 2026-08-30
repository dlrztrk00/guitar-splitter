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

# Finder hands an app a minimal PATH without Homebrew on it. The code resolves
# ffmpeg by absolute path anyway, but a sane PATH costs nothing.
export PATH="/usr/local/bin:/opt/homebrew/bin:\$PATH"

exec "\$REPO/venv/bin/python" app.py --port "\$PORT"
LAUNCHER
chmod +x "$APP/Contents/MacOS/GuitarSplit"

# Icon. Drawn by icon.py rather than a rasteriser — see the note there about
# qlmanage painting white corners onto anything with transparency.
if [ -x ./venv/bin/python ]; then
  ./venv/bin/python icon.py "$APP/Contents/Resources/GuitarSplit.icns"
else
  echo "note: no venv yet, skipping the icon (run ./setup.sh then ./make_app.sh)"
fi

touch "$APP"
echo "Built $APP"
