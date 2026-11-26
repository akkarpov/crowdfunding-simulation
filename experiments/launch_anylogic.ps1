param(
  [ValidateSet('DES','DES-Simulation','DES-Count','DES-Zero','DES-Stress',
               'Tuning','Variation','OptQuest','Markov','ABM','ABM-Base',
               'ABM-Mixed','ABM-Priority','SD-Base','SD-Demand','SD-Shock','SD-Adaptive','SD-Growth')]
  [string]$Task = 'DES',
  [string]$AnyLogicInstall = 'D:/AnyLogicPLE898',
  [ValidatePattern('^[a-zA-Z0-9_-]+$')]
  [string]$RunId
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$app = Join-Path $AnyLogicInstall 'AnyLogic.exe'
if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
  throw "Укажите каталог AnyLogic через параметр -AnyLogicInstall."
}
$des = 'models/des/CrowdfundingPlatform.alp'
$markov = 'models/markov/ManualQueueMarkov.alp'
$abm = 'models/abm/CrowdfundingAgents.alp'
$sd = 'models/sd/PlatformDynamics.alp'
$tasks = @{
  'DES'            = @($des,'Research')
  'DES-Simulation' = @($des,'Simulation')
  'DES-Count'      = @($des,'CountCheck')
  'DES-Zero'       = @($des,'ZeroLoad')
  'DES-Stress'     = @($des,'Congestion')
  'Tuning'         = @($des,'Tuning')
  'Variation'      = @($des,'Variation')
  'OptQuest'       = @($des,'OptQuest')
  'Markov'         = @($markov,'Research')
  'ABM'            = @($abm,'Simulation')
  'ABM-Base'       = @($abm,'Research')
  'ABM-Mixed'      = @($abm,'Mixed')
  'ABM-Priority'   = @($abm,'MixedPriority')
  'SD-Base'        = @($sd,'Research')
  'SD-Demand'      = @($sd,'RisingDemand')
  'SD-Shock'       = @($sd,'CapacityShock')
  'SD-Adaptive'    = @($sd,'Adaptive')
  'SD-Growth'      = @($sd,'Endogenous')
}
$chosen = $tasks[$Task]
$file = (Resolve-Path -LiteralPath (Join-Path $root $chosen[0])).Path
$runName = 'run-' + $Task.ToLowerInvariant()
if ($RunId) { $runName += '-' + $RunId }
$runDirectory = (New-Item -ItemType Directory -Force (Join-Path $root ('.local/' + $runName))).FullName
$runWorkspace = Join-Path $runDirectory 'workspace'
$runConfiguration = (New-Item -ItemType Directory -Force (Join-Path $runDirectory 'configuration')).FullName
$config = Join-Path $runConfiguration 'config.ini'
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
  $template = Join-Path $AnyLogicInstall 'configuration/config.ini'
  Copy-Item -LiteralPath $template -Destination $config
}
$argumentList = @('-configuration', ('"' + $runConfiguration + '"'),
                  '-data', ('"' + $runWorkspace + '"'), '-r',
                  ('"' + $file + '"'), $chosen[1])
$runTemp = (New-Item -ItemType Directory -Force (Join-Path $runDirectory 'temp')).FullName
$process = [Diagnostics.ProcessStartInfo]::new()
$process.FileName = $app
$process.WorkingDirectory = $AnyLogicInstall
$process.Arguments = $argumentList -join ' '
$process.UseShellExecute = $false
$process.EnvironmentVariables['TEMP'] = $runTemp
$process.EnvironmentVariables['TMP'] = $runTemp
[void][Diagnostics.Process]::Start($process)
Write-Output ("Выгрузки сохраняются в " + $runTemp)
