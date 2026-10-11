param(
    [ValidateSet('4b', '1.7b')][string]$Size = '4b',
    [ValidateSet('q4_k_m', 'q8_0')][string]$Quant = 'q4_k_m',
    [ValidateSet('auto', 'cpu', 'cuda', 'vulkan')][string]$Device = 'auto',
    [ValidateSet('auto', 'cpu', 'cuda', 'vulkan')][string]$Runtime = 'auto',
    [ValidateRange(1024, 65535)][int]$Port = 8017,
    [switch]$SkipDownload,
    [switch]$SkipCLM
)

$ErrorActionPreference = 'Stop'
$upstreamRevision = 'b9ba007ee4d2928bbab5b1d8bfe9009c3696b6de'
$upstreamPath = Join-Path $PSScriptRoot '.runtime/rizzo-flow'
$clmProcess = $null

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program terminato con codice $LASTEXITCODE." }
}

foreach ($program in @('git', 'uv')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) {
        throw "Installa $program e riapri PowerShell. Vedi README.md."
    }
}

if (-not (Test-Path -LiteralPath $upstreamPath)) {
    Invoke-Checked git @('clone', '--no-checkout', 'https://github.com/Rizzo-AI-Academy/rizzo-flow.git', $upstreamPath)
    Invoke-Checked git @('-C', $upstreamPath, 'checkout', '--detach', $upstreamRevision)
}
$actualRevision = & git -C $upstreamPath rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actualRevision -ne $upstreamRevision) {
    throw "La copia locale di Rizzo Flow non corrisponde alla revisione prevista: $upstreamRevision."
}

Push-Location $upstreamPath
try {
    Invoke-Checked uv @('sync', '--locked', '--python', '3.11')
    Invoke-Checked uv @('pip', 'install', '--python', '.venv/Scripts/python.exe', '-r', (Join-Path $PSScriptRoot 'requirements-demo.txt'))
    if (-not $SkipDownload) {
        Write-Host 'Preparazione del modello locale. Il primo avvio scarica circa 2,6 GB (4B Q4) piu il runtime.'
        Invoke-Checked uv @('run', '--python', '3.11', '--no-sync', 'rizzo', 'download', '--size', $Size, '--quant', $Quant, '--runtime', $Runtime)
    }
    if (-not $SkipCLM -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.runtime/clm-local/installed'))) {
        $clmRunning = $false
        try {
            $clmStatus = Invoke-RestMethod 'http://127.0.0.1:8700/health' -TimeoutSec 3
            $clmRunning = $clmStatus.ok -and $clmStatus.embedder
        } catch { }
        if (-not $clmRunning) {
            $clmPython = Join-Path $PSScriptRoot '.runtime/clm-local/.venv/Scripts/python.exe'
            $clmRunner = Join-Path $PSScriptRoot 'clm_local.py'
            $clmProcess = Start-Process -FilePath $clmPython -ArgumentList @('"' + $clmRunner + '"') -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $PSScriptRoot '.runtime/clm-local/server.log') `
                -RedirectStandardError (Join-Path $PSScriptRoot '.runtime/clm-local/server-error.log')
            Write-Host 'Caricamento CLM locale. Rizzo viene caricato dopo CLM per limitare il picco di memoria.'
            $clmStartupWatch = [Diagnostics.Stopwatch]::StartNew()
            while (-not $clmRunning -and -not $clmProcess.HasExited -and $clmStartupWatch.Elapsed.TotalSeconds -lt 300) {
                try {
                    $clmStatus = Invoke-RestMethod 'http://127.0.0.1:8700/health' -TimeoutSec 2
                    $clmRunning = $clmStatus.ok -and $clmStatus.embedder
                } catch { }
                if (-not $clmRunning) { Start-Sleep -Milliseconds 750 }
            }
            $clmStartupWatch.Stop()
            if (-not $clmRunning) { Write-Warning 'CLM non ancora pronto: controlla .runtime/clm-local/server-error.log. La demo continua ad avviarsi.' }
        }
    }
    Write-Host "Caricamento del modello. Poi apri http://127.0.0.1:$Port (Ctrl+C per arrestare)."
    Invoke-Checked uv @('run', '--python', '3.11', '--no-sync', 'python', (Join-Path $PSScriptRoot 'app.py'), '--size', $Size, '--quant', $Quant, '--device', $Device, '--port', "$Port")
}
finally {
    if ($clmProcess -and -not $clmProcess.HasExited) {
        # The Windows venv launcher can own a second Python process.
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($clmProcess.Id)" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*clm_local.py*' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $clmProcess.Id -ErrorAction SilentlyContinue
    }
    Pop-Location
}
