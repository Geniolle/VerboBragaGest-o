param(
    [string]$ProjectDir = "C:\workspace\pastoreio-orquestrador"
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $ProjectDir
uv --cache-dir .uv-cache run python scripts\Servidor\executar_colaborador_agendado.py --aplicar
