<#
.SYNOPSIS
    Меню управления модами EU5: мастерская, папка игры, этот репозиторий.

.DESCRIPTION
    Запусти без аргументов — откроется меню:

      1  мастерская: проверить, скачать свежие в игру, обновить копии
      2  все моды: выбрать мод и решить, что с ним делать
      3  всё сразу: обновить всё, убрать отсутствующее, наши в игру
      4  забрать из игры: логи, файлы игры, дампы API

    Ничего не пересобирает и не проверяет: это работа сессии.

    Это просто запускалка: вся работа в tools\mods.py, чтобы одно и то же
    поведение было и здесь, и в любой другой оболочке. Все аргументы уходят
    туда как есть.

.EXAMPLE
    .\tools\mods.ps1

.EXAMPLE
    .\tools\mods.ps1 check

.EXAMPLE
    .\tools\mods.ps1 --workshop "D:\SteamLibrary\steamapps\workshop\content"
#>

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Arguments
)

$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$toolsDir = if ($PSScriptRoot) { $PSScriptRoot }
            else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoDir  = Split-Path -Parent $toolsDir

. (Join-Path $toolsDir 'find_python.ps1')

$python = Find-Python
if (-not $python) {
    Write-Host ''
    Write-Host 'Без Python это меню не запустится.' -ForegroundColor Red
    Write-Host 'Поставить один раз:' -ForegroundColor Yellow
    Write-Host '  winget install -e --id Python.Python.3.12' -ForegroundColor Yellow
    exit 1
}

# Меню говорит по-русски, а PowerShell читает вывод программы через канал, а не
# через консоль - без этого Python садится на кодовую страницу системы и падает
# на первой же русской строке.
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

Push-Location $repoDir
try {
    & $python (Join-Path $toolsDir 'mods.py') @Arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
