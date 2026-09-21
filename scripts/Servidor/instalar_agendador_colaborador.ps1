param(
    [string]$TaskName = "Pastoreio-Colaborador-Orquestrador",
    [string]$ProjectDir = "C:\workspace\pastoreio-orquestrador"
)

$ErrorActionPreference = "Stop"

$Uv = (Get-Command uv -ErrorAction Stop).Source
$Script = Join-Path $ProjectDir "scripts\Servidor\executar_colaborador_agendado.py"

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Script nao encontrado: $Script"
}

$Action = New-ScheduledTaskAction `
    -Execute $Uv `
    -Argument "--cache-dir .uv-cache run python scripts\Servidor\executar_colaborador_agendado.py --aplicar" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Executa o cockpit Colaborador do Pastoreio a cada minuto. O runner tem lock e mantem apenas o ultimo log." `
    -Force | Out-Null

Write-Host "Agendador instalado/atualizado: $TaskName"
Write-Host "Frequencia: 1 minuto"
Write-Host "Modo: APLICAR"
Write-Host "Concorrencia: IgnoreNew + lock no runner"
Write-Host "Log unico: $(Join-Path $ProjectDir 'runtime\colaborador_ultimo.log')"
