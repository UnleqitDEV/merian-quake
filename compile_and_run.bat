@echo off
REM ...existing code...

set "ROOT=%~dp0"
pushd "%ROOT%"

meson setup build
meson compile -C build

REM im Build-Ordner starten und danach zurückkehren
meson devenv -C build cmd /c "%ROOT%build\merian-quake.exe -basedir %ROOT%quakedir\\"

popd