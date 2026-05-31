python -m py_compile app/agrandiz_gui.py

rm -rf dist/Agrandiz.app
rm -rf "$HOME/Library/Application Support/Agrandiz"

scripts/build_macos_app.sh
dist/Agrandiz.app/Contents/MacOS/agrandiz
