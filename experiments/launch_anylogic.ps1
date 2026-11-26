param(
  [ValidateSet('DES','DES-Simulation','DES-Count','DES-Zero','DES-Stress',
               'Tuning','Variation','OptQuest','Markov','ABM','ABM-Base',
               'ABM-Mixed','ABM-Priority','SD-Base','SD-Demand','SD-Shock','SD-Adaptive','SD-Growth')]
  [string]$Task = 'DES',
  [string]$AnyLogicInstall = 'D:/AnyLogicPLE898'
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
$runWorkspace = Join-Path $root ('.local/run-' + $Task.ToLowerInvariant())
$argumentList = @('-data', ('"' + $runWorkspace + '"'), '-r',
                  ('"' + $file + '"'), $chosen[1])
Start-Process -FilePath $app -WorkingDirectory $AnyLogicInstall -ArgumentList $argumentList
