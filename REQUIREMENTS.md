# Матрица требований

Источники требований — [задание преподавателя](ASSIGNMENT.md) и подробное ТЗ. Статус приведён для каждого вида проверки.

| ID | Требование | Источник | Этап | Артефакт | Проверка | Статус |
|---|---|---|---:|---|---|---|
| E1 | Ресурсы, сущности, маршруты, остановка, деньги и SLA | ТЗ §1 | 1 | SPECIFICATION.md, config/baseline.json, figures/platform.* | Сверка и проверка параметров и схемы | VERIFIED |
| E1B | Соответствие исходному заданию преподавателя | Исходное задание §1 | 1 | ASSIGNMENT.md, SPECIFICATION.md | Сверка с текстом и описанием системы | VERIFIED |
| E2A | Нативный DES на Process Modeling Library | ТЗ §2 | 2 | models/des/ | Базовый прогон на 10 000 завершений и независимая проверка горизонта 2160 ч | VERIFIED |
| E2B | Балансы, R1–R8, остановка, метрики, независимые платежи в эталоне | ТЗ §2 | 2 | analysis/des.py, results/raw/des_checks.json | Восемь проверок | VERIFIED |
| E2C | 2D и 3D на одной нативной модели | ТЗ §2 | 2 | models/add_views.py, models/des/CrowdfundingPlatform.alp | Выполнен стохастический 2D/3D-прогон, опубликованы результаты и графики R1–R8 | VERIFIED |
| E3 | Узкие места, зрелый SLA, сегменты, мощность | ТЗ §3 | 3 | experiments/capacity.py, results/processed/capacity_*.csv | 120 прогонов, интервалы и парные сравнения | VERIFIED (эталонный DES) |
| E4A | Нативный Parameter Variation и управляемые прогоны | ТЗ §4.1–4.2 | 4 | CrowdfundingPlatform.alp, experiments/optimization.py | Пять контрольных положений ползунков и 48 нативных репликаций с видимой таблицей | VERIFIED |
| E4B | OptQuest ≥100 итераций и ≥3 повторов | ТЗ §4.3 | 4 | CrowdfundingPlatform.alp, figures/native_optquest.png | 100 итераций и 300 результатов, проверены таблица и график сходимости | VERIFIED |
| E4C | Независимый поиск и проверка выбранного решения | ТЗ §4.3 | 4 | results/raw/search.jsonl, results/processed/optquest_winner_validation.csv | 100 × 3, независимые 90-дневные прогоны победителя OptQuest с десятью новыми seeds | VERIFIED |
| E5A | M/M/c/K в AnyLogic | ТЗ §5 | 5 | models/markov/ManualQueueMarkov.alp | Нативные 240 часов, 27 вероятностей, валидация нормировки и оптимизации | VERIFIED |
| E5B | Уравнения, стационарная проверка и согласованный DES | ТЗ §5 | 5 | analysis/markov.py, results/processed/markov_comparison.csv | Нормировка и интервалы 10 прогонов | VERIFIED |
| E6A | Нативный Statechart платформы и 2D/3D | ТЗ §6 | 6 | models/abm/CrowdfundingAgents.alp, figures/native_abm_mixed.png | Две популяции, четыре нативных прогона, проверен экран 2D/3D | VERIFIED |
| E6B | Гетерогенность и приоритеты | ТЗ §6 | 6 | results/processed/abm_summary.csv, results/processed/abm_native.csv | База совпала с DES, 90 эталонных прогонов классов, направление эффекта подтверждено в AnyLogic | VERIFIED |
| E7A | Нативные накопители, обратные связи и сценарии | ТЗ §7 | 7 | models/sd/PlatformDynamics.alp, figures/sd_native.png | База, рост спроса и шок по 480 ч, сверка траекторий и балансов | VERIFIED |
| E7B | Сценарии SD, балансы и устойчивость шага | ТЗ §7 | 7 | analysis/sd.py, results/processed/sd_checks.csv | Пять сценариев, сравнение с 6 повторами DES | VERIFIED |
| E8A | Отчёт, сравнение, альтернативы и защита | ТЗ §8 | 8 | report/, results/processed/decision_matrix.csv | Воспроизводимые цифры, DOCX, 13 проверенных страниц PDF и 20 вопросов для защиты | VERIFIED |
| E8B | Оптнер 3–9 и оценка альтернатив | Исходное задание §8.2 | 8 | stages/08-system-analysis.md | Использована опубликованная нумерация Волковой и Денисова | VERIFIED по выбранному источнику |
