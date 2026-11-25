# Имитационное моделирование краудфандинговой платформы

Исследование очередей, технических сроков и мощности платформы с помощью DES, ABM, SD и марковской модели.

- [Спецификация модели](SPECIFICATION.md)
- [Матрица требований](REQUIREMENTS.md)
- [Состояние работ и проверок](STATUS.md)
- [Исходник схемы](figures/platform.mmd) и [схема SVG](figures/platform.svg)

Базовые параметры хранятся в `config/baseline.json`. Проверка параметров и построение схемы: `python analysis/verify_spec.py`.


## Эталонный дискретно-событийный расчёт

Из корня проекта запустите команды.

```powershell
python -m pip install -r requirements.txt
python experiments/check_des.py
python experiments/run_des.py --seed 2501 --output results/raw/des_baseline.json
python experiments/capacity.py
python analysis/capacity_results.py
```

Первичные результаты серии находятся в `results/raw/capacity.jsonl`, обработанные средние и интервалы доступны в `results/processed/capacity_summary.csv`. Для сравнения 12 конфигураций использовано по 10 повторений на 2160 ч. Нативная модель и эталон проверяются отдельно.
