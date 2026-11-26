# Имитационное моделирование краудфандинговой платформы

Исследование очередей, сроков обслуживания и мощности платформы методами DES, ABM, SD и M/M/c/K.

- [Отчёт PDF](report/Отчёт.pdf) · [DOCX](report/Отчёт.docx) · [Редактируемый Markdown](report/REPORT.md) · [Защита и вопросы](report/DEFENSE.md)
- [Задание преподавателя](ASSIGNMENT.md) · [Спецификация](SPECIFICATION.md) · [Матрица требований](REQUIREMENTS.md) · [Приёмка и ограничения](STATUS.md)
- [Схема ресурсов](figures/platform.svg) · [Исходник схемы](figures/platform.mmd)
- [Файлы и запуск AnyLogic](models/README.md) · [Протокол мощности](experiments/PROTOCOL.md) · [Постановка оптимизации](experiments/OPTIMIZATION.md)

## Материалы по этапам

| Этап | Результат |
|---|---|
| 1 | [Постановка и спецификация](SPECIFICATION.md) |
| 2 | [Нативная DES и проверочные сценарии](stages/02-des.md) |
| 3 | [SLA, узкие места и мощность](stages/03-capacity.md) |
| 4 | [Эксперименты и многокритериальная оптимизация](stages/04-experiments.md) |
| 5 | [Динамика вероятностей](stages/05-markov.md) |
| 6 | [Агенты и гетерогенность](stages/06-agents.md) |
| 7 | [Системная динамика](stages/07-system-dynamics.md) |
| 8 | [Сравнение и анализ по Оптнеру](stages/08-system-analysis.md) |

## Запуск AnyLogic

```powershell
.\experiments\launch_anylogic.ps1 -Task DES
```

В [перечне моделей](models/README.md) указаны команды для каждого эксперимента.

## Проверочный расчёт

Требуется Python 3.11. Команды выполняются из корня проекта.

```powershell
python -m pip install -r requirements.txt
python analysis/verify_spec.py
python experiments/check_des.py
python experiments/run_des.py --seed 2501 --output results/raw/des_baseline.json
```

`--rate`, `--r3` и `--hours` переопределяют интенсивность, каналы R3 и модельные часы. `--trace` сохраняет трассу. Без `--fixed` действует остановка по первому из тайм-горизонта и счётчика.

## Воспроизведение серий

Готовые результаты в `results/raw`. Команды читают завершённые серии из этого каталога. Для пересчёта после изменения параметров или модели задайте `$env:CROWDFUNDING_REBUILD = '1'`. Используйте `$env:CROWDFUNDING_WORKERS = '1'` для последовательного прохода. Первичные записи содержат сценарии, seeds, окно, причину остановки и метрики.

```powershell
python experiments/capacity.py
python analysis/capacity_results.py
python analysis/resource_diagnostics.py
python experiments/optimization.py
python analysis/teacher_results.py 4
python analysis/teacher_results.py 4 --verify-native-optquest
python analysis/markov.py
python analysis/teacher_results.py 5
python experiments/abm.py
python analysis/sd.py
python experiments/stress.py
python analysis/compare_results.py
python report/build_report.py
```

Для печатной версии укажите путь к установленному Chromium.

```powershell
python report/export_pdf.py 'D:/AnyLogicPLE898/chromium/chromium-win64/chrome.exe'
```

Таблицы интервалов находятся в `results/processed`, графики в `figures`. Полные серии относятся к эталонным вычислениям Python. Нативные ALP и статус их приёмки приведены отдельно.
