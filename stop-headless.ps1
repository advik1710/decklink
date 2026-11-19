$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidPath = Join-Path $root '.decklink.pid'
if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Output 'No headless DeckLink host is running.'
    exit 0
}

$hostPid = 0
[void][int]::TryParse((Get-Content -LiteralPath $pidPath -Raw), [ref]$hostPid)
if ($hostPid -gt 0) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $hostPid" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -like '*host.py*') {
        Stop-Process -Id $hostPid -Force
        Write-Output 'DeckLink stopped.'
    } else {
        Write-Output 'The recorded host is no longer running.'
    }
}
Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
