# Модели AnyLogic 8.9.8

Откройте ALP и запустите нужный эксперимент из дерева проекта. Для установки на диске D доступен общий запуск из корня репозитория.

```powershell
.\experiments\launch_anylogic.ps1 -Task DES
```

| Раздел | Модель | Значения `-Task` |
|---|---|---|
| 2. DES | [CrowdfundingPlatform.alp](des/CrowdfundingPlatform.alp) | DES, DES-Simulation, DES-Count, DES-Zero, DES-Stress |
| 4. Эксперименты | [CrowdfundingPlatform.alp](des/CrowdfundingPlatform.alp) | Tuning, Variation, OptQuest |
| 5. Вероятности | [ManualQueueMarkov.alp](markov/ManualQueueMarkov.alp) | Markov |
| 6. Агентная модель | [CrowdfundingAgents.alp](abm/CrowdfundingAgents.alp) | ABM, ABM-Base, ABM-Mixed, ABM-Priority |
| 7. Системная динамика | [PlatformDynamics.alp](sd/PlatformDynamics.alp) | SD-Base, SD-Demand, SD-Shock, SD-Adaptive, SD-Growth |

`DES` использует базовую стохастическую нагрузку и первое условие остановки из 10 000 терминальных проектов и 2160 модельных часов. `DES-Simulation` проводит три заданных проекта по R1–R8. `DES-Count` проверяет остановку на двух проектах. `DES-Zero` задаёт нулевой поток, `DES-Stress` создаёт перегрузку.

DES использует цепочку Enter → TimeMeasureStart → Service → TimeMeasureEnd → Exit для каждого ресурса. У каждого Service собственный ResourcePool. Два вида операций используют общую очередь R5. Технические агенты возвращаются в пул; объекты проектов, платежей и обращений сохраняют собственные параметры и идентификаторы.

`Tuning` задаёт интенсивность нагрузки и число каналов R3. `Variation` использует 16 комбинаций четырёх факторов с тремя повторами. `OptQuest` максимизирует взвешенную функцию потока завершений и суммы загрузки при четырёх ограничениях, 100 итерациях и трёх повторах. [Эксперименты и цели](../stages/04-experiments.md)

Агентная модель содержит две популяции с собственными диаграммами состояний. Для сравнительного эксперимента `ABM-Mixed` доля тяжёлых проектов равна 25%. В `ABM-Priority` действует обслуживание лёгких проектов с приоритетом без прерывания.

`SD-Demand` поднимает внешний поток до 6,5 проекта/ч. `SD-Shock` приостанавливает часть мощности, `SD-Adaptive` добавляет управление каналами, `SD-Growth` включает обратную связь спроса.

При запуске через скрипт временный каталог Java находится в `.local/run-<задача>/temp`. При запуске из IDE используется системный временный каталог Java. Приёмочные скрипты принимают путь к выгрузкам через `--source`. DES и ABM создают файлы `crowdfunding-native-<сценарий>-<seed>-*.csv`. Серии вероятностей и SD имеют префикс `crowdfunding-series-`. Перед проверкой сопоставьте время создания результата с запуском. [Приёмка](../STATUS.md)

В окне эксперимента нажмите кнопку запуска в нижней панели, если расчёт ожидает команды. Для отдельного повторного прогона передайте `-RunId repeat`; выгрузки попадут в `.local/run-<задача>-repeat/temp`. [Запуск экспериментов в справке AnyLogic](https://www.anylogic.help/anylogic/running/run-simulation.html)

## Пересборка

```powershell
python models/build_platform.py D:/AnyLogicPLE898
python models/add_native_experiments.py D:/AnyLogicPLE898
python models/add_views.py D:/AnyLogicPLE898
python models/build_population.py D:/AnyLogicPLE898
python models/build_continuous.py
```

ALP самодостаточны для запуска. Сборщики DES и ABM используют примеры установленного AnyLogic как шаблоны. Для пересчёта непрерывных моделей требуются результаты `python analysis/markov.py` и `python analysis/sd.py`.
