<#
.SYNOPSIS
    Меню управления модами EU5: мастерская, папка игры, этот репозиторий.

.DESCRIPTION
    Запусти без аргументов — откроется меню:

      1  обновить моды в Steam: сверить сборки, скачать, заменить
      2  обновить копии в репозитории (reference / playset)
      3  мои моды: список, что где лежит, перенос между ними
      4  поставить наши моды в игру
      5  готов ли наш мод к мастерской
      6  забрать диагностику из игры
      7  забрать из игры файлы или логи
      8  перечитать всё заново
      9  после обновления игры: обновить в репозитории всё и пересобрать

    Пункт 4 — это то, что заменяет обновление через Steam для наших модов:
    он тянет main и подменяет копию в Documents\Paradox Interactive\Europa
    Universalis V\mod целиком, а потом перечитывает её с диска и говорит,
    сошлось или нет.

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
