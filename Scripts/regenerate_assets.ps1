# Rebuilds every Advanced Fluid Buffer asset from Art/ in the right order:
#   1. create_assets.py (commandlet): meshes, plain materials, icons, Build/Desc/Recipe Blueprints,
#      ladder, colorable Mesh component. Re-importing the mesh drops its LODs and swatch materials.
#   2. apply_lods_and_swatches.py (full editor, -nullrhi, quits itself): LOD1/LOD2 and the swatch
#      materials. The LOD helpers only work with GIsEditor, hence the full editor binary here.
# Needs the editor target built. Takes about 3 minutes. Logs go to C:\SF\SML\Saved\Logs\AFB-*.log.
$ErrorActionPreference = "Stop"
$engine  = "C:\Program Files\Unreal Engine - CSS\Engine\Binaries\Win64"
$project = "C:\SF\SML\FactoryGame.uproject"
$logs    = "C:\SF\SML\Saved\Logs"

Write-Host "1/2 create_assets.py ..." -ForegroundColor Cyan
& "$engine\UnrealEditor-Cmd.exe" $project -run=pythonscript "-script=$PSScriptRoot\create_assets.py" `
    -unattended -nosplash -NoLogTimes "-abslog=$logs\AFB-create.log" | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "create_assets.py failed (exit $LASTEXITCODE), see $logs\AFB-create.log" -ForegroundColor Red; exit 1 }

Write-Host "2/2 apply_lods_and_swatches.py ..." -ForegroundColor Cyan
$p = Start-Process "$engine\UnrealEditor.exe" -PassThru -Wait -ArgumentList @(
    "`"$project`"", "-ExecutePythonScript=`"$PSScriptRoot\apply_lods_and_swatches.py`"",
    "-unattended", "-nosplash", "-nullrhi", "-NoLogTimes", "-abslog=`"$logs\AFB-lods-swatches.log`"")
if (Select-String -Path "$logs\AFB-lods-swatches.log" -Pattern "LogPython: Error" -Quiet) {
    Write-Host "apply_lods_and_swatches.py reported Python errors, see $logs\AFB-lods-swatches.log" -ForegroundColor Red; exit 1
}
Write-Host "Assets regenerated." -ForegroundColor Green
