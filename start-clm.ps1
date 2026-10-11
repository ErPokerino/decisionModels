param(
    [switch]$Install,
    [ValidateRange(1024, 65535)][int]$Port = 8700,
    [ValidateRange(1, 32)][int]$Threads = 6
)
$ErrorActionPreference = 'Stop'
$runtimePath = Join-Path $PSScriptRoot '.runtime/clm-local'
$referencePath = Join-Path $PSScriptRoot '.runtime/clm-reference'
$referenceRevision = 'd5f9ef0fd9bde185df0ceaad4f4ecc6cfe8c34f6'
$pythonPath = Join-Path $runtimePath '.venv/Scripts/python.exe'
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program terminato con codice $LASTEXITCODE." }
}
if ($Install) {
    if (-not (Test-Path -LiteralPath $referencePath)) {
        Invoke-Checked git @('clone', '--no-checkout', 'https://github.com/Contrastive-LM/CLM.git', $referencePath)
        Invoke-Checked git @('-C', $referencePath, 'checkout', '--detach', $referenceRevision)
    }
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        Invoke-Checked uv @('venv', '--python', '3.11', (Join-Path $runtimePath '.venv'))
    }
    Invoke-Checked uv @('pip', 'install', '--python', $pythonPath, 'torch==2.14.1', '--index-url', 'https://download.pytorch.org/whl/cpu')
    Invoke-Checked uv @('pip', 'install', '--python', $pythonPath, '-r', (Join-Path $PSScriptRoot 'requirements-clm.txt'))
    Invoke-Checked $pythonPath @((Join-Path $PSScriptRoot 'setup_clm.py'), '--range-download')
}
if (-not (Test-Path -LiteralPath (Join-Path $runtimePath 'installed'))) {
    throw 'CLM non installato. Esegui .\start-clm.ps1 -Install (download iniziale ~16 GB).'
}
$actualRevision = & git -C $referencePath rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actualRevision -ne $referenceRevision) { throw 'Revisione CLM upstream non corrispondente.' }
Invoke-Checked $pythonPath @((Join-Path $PSScriptRoot 'clm_local.py'), '--port', "$Port", '--threads', "$Threads")
