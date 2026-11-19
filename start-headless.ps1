$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidPath = Join-Path $root '.decklink.pid'

if (Test-Path -LiteralPath $pidPath) {
    $oldPid = 0
    [void][int]::TryParse((Get-Content -LiteralPath $pidPath -Raw), [ref]$oldPid)
    if ($oldPid -gt 0) {
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $oldPid" -ErrorAction SilentlyContinue
        if ($existing -and $existing.CommandLine -like '*host.py*') {
            Write-Output 'DeckLink is already running.'
            exit 0
        }
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$hostPath = Join-Path $root 'host.py'
$stdout = Join-Path $root 'decklink-host.log'
$stderr = Join-Path $root 'decklink-error.log'
$process = Start-Process -FilePath $python -ArgumentList @($hostPath, '--no-open') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding Ascii
Start-Sleep -Milliseconds 700
$process.Refresh()
if ($process.HasExited) {
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    throw 'DeckLink exited during startup. Check decklink-error.log.'
}
Write-Output 'DeckLink started in the background. Use stop.bat to stop it.'
