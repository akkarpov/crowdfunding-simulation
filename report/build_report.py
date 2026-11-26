"""Генерирует редактируемый отчёт Markdown и DOCX из результатов."""
from collections import defaultdict
import csv
import json
from pathlib import Path
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.capacity_results import PROCESSED, RAW, ROOT, interval, series, METRICS
from experiments.capacity import save_csv

REPORT = ROOT / "report"


def csvdata(filename, fields):
    return {tuple(r[k] for k in fields): r
            for r in csv.DictReader((PROCESSED / filename).open(encoding="utf-8"))}


def fmt(n, k=2):
    number = float(n)
    if abs(number) < .5 * 10 ** -k:
        number = 0
    return f"{number:.{k}f}".replace(".", ",")


def ci(r, factor=1, digits=2):
    return f"{fmt(factor*float(r['mean']), digits)} [{fmt(factor*float(r['lo']), digits)}–{fmt(factor*float(r['hi']), digits)}]"


def create_markdown():
    capacity = csvdata("capacity_summary.csv", ["scenario", "metric"])
    pairs = csvdata("capacity_differences.csv", ["scenario", "metric"])
    validation = csvdata("validation_summary.csv", ["scenario", "metric"])
    weighted = csvdata("multiobjective_validation.csv", ["scenario", "metric"])
    agents = csvdata("abm_summary.csv", ["scenario", "group", "metric"])
    markov = json.loads((RAW / "markov.json").read_text())
    sd = csvdata("sd_checks.csv", ["scenario"])
    segmentation = csvdata("cohort_segments.csv", ["segment","group"])
    knee = csvdata("capacity_knee.csv", ["before","after","metric"])
    stress = defaultdict(list)
    for row in series("stress.jsonl"):
        stress[row["scenario"]].append(row)
    s = {key: interval(METRICS["sla"](r) for r in seq) for key, seq in stress.items()}
    agent_runs = {(r["scenario"],r["seed"]):r for r in series("abm.jsonl")}
    agent_priority = interval(agent_runs["heavy_25_priority",seed]["groups"]["heavy"]["sla"]["failure"]
                      - agent_runs["heavy_25_fifo",seed]["groups"]["heavy"]["sla"]["failure"]
                      for seed in range(6101,6111))

    alternatives = [
        ("База", "base", "base", "Исходная"),
        ("Добавить AI-канал", "r2_3", "r2_3", "Низкая"),
        ("Добавить ручной канал", "r3_3", "r3_3", "Низкая"),
        ("Добавить платёжный канал", "r4_5", "r4_5", "Низкая"),
        ("R2: 2→1, R3: 2→3", "redistribute", "redistribute", "Средняя"),
        ("Перераспределить и усилить R4", "opt_008", "redistribute_r4_5", "Средняя"),
    ]
    lines = ["| Вариант | Завершения, проект/ч | P95, ч | SLA, % | Стоимость | Отказы, % | SLA при 6/ч, % | Сложность |",
             "|---|---:|---:|---:|---:|---:|---:|---|"]
    matrix = []
    for name, key, stress_key, complexity in alternatives:
        table = validation if key.startswith("opt") else capacity
        get = lambda field: table[key, field]
        record = dict(scenario=key, name=name, throughput=get("throughput")["mean"], p95=get("p95")["mean"],
                      sla=get("sla")["mean"], cost=get("sla")["cost"], technical=get("technical")["mean"],
                      stress_sla=s[stress_key]["mean"], stress_sla_hi=s[stress_key]["hi"],
                      complexity=complexity)
        matrix.append(record)
        lines.append("| " + " | ".join([name, fmt(record["throughput"]), fmt(record["p95"]),
            fmt(100*float(record["sla"])), record["cost"], fmt(100*float(record["technical"])),
            fmt(100*record["stress_sla"]), complexity]) + " |")
    save_csv(PROCESSED / "decision_matrix.csv", matrix)
    decision_table = "\n".join(lines)
    a = lambda key, metric: ci(capacity[key, metric], 100 if metric in {"sla","technical"} else 1)
    v = lambda key, metric: ci(validation[key, metric], 100 if metric in {"sla","payment_sla"} else 1)
    b = lambda key, group, metric: ci(agents[key, group, metric], 100 if metric == "sla" else 1)
    m = markov["analytical"]
    c = markov["platform"]
    native = ROOT / "results/native/experiments"
    native_summary = ""
    best_path = native / "optquest_best.csv"
    if best_path.is_file():
        with best_path.open(encoding="utf8", newline="") as stream:
            best = next(csv.DictReader(stream))
        settings = ", ".join(str(int(float(best[k]))) for k in ("r2", "r3", "r4"))
        native_summary = (
            "\n\nНативный OptQuest выполнил 100 итераций по три репликации. "
            f"Лучший допустимый вариант R2/R3/R4 = {settings} за {fmt(best['cost'], 0)} у.е. "
            f"дал {fmt(best['throughput'], 3)} завершения/ч, {fmt(best['payouts'], 3)} выплаты/ч "
            f"и {fmt(100 * float(best['sla_failure']), 3)}% нарушений SLA. "
            f"Значение цели {fmt(best['objective'], 6)}. Этот результат относится к 168-часовому поиску."
        )
        if (native / "tuning.csv").is_file() and (native / "variation.csv").is_file():
            native_summary += (
                " Отдельно проверены пять положений двух нативных ползунков и "
                "16 комбинаций Parameter Variation, по три репликации на комбинацию."
            )
        if (PROCESSED / "optquest_winner_validation.csv").is_file():
            confirmation = csvdata("optquest_winner_validation.csv", ["metric"])
            native_summary += (
                " На десяти новых seeds эталонной DES за 2160 ч получены SLA "
                f"{ci(confirmation['sla_failure',], 100, 3)}% "
                f"и {ci(confirmation['payouts',], digits=3)} выплаты/ч."
            )
        if (ROOT / "figures/native_optquest.png").is_file():
            native_summary += (
                "\n\n![Рисунок 6а. Нативная сходимость OptQuest и таблица решений.]"
                "(../figures/native_optquest.png)"
            )
    native_agents = ""
    if (PROCESSED / "abm_native.csv").is_file():
        comparison = csvdata("abm_native.csv", ["case"])
        des, base, mix, priority = (comparison[name,] for name in (
            "research", "abm_base", "abm_mixed", "abm_mixedpriority"
        ))
        native_agents = (
            f"\n\nВ AnyLogic при общем seed 2501 базовые DES и ABM дали "
            f"{fmt(des['throughput'], 3)} и {fmt(base['throughput'], 3)} завершения/ч. "
            f"Средняя суммарная очередь составила {fmt(des['mean_queue'])} и "
            f"{fmt(base['mean_queue'])} заявки. При добавлении тяжёлого класса в ABM "
            f"P95 ожидания лёгких вырос с {fmt(base['light_p95_r3_h'])} "
            f"до {fmt(mix['light_p95_r3_h'])} ч. Приоритет лёгких снизил их P95 "
            f"до {fmt(priority['light_p95_r3_h'])} ч и поднял P95 тяжёлых с "
            f"{fmt(mix['heavy_p95_r3_h'])} до {fmt(priority['heavy_p95_r3_h'])} ч. "
            "Это результаты отдельных нативных прогонов."
        )
        if (ROOT / "figures/native_abm_mixed.png").is_file():
            native_agents += (
                "\n\n![Рисунок 8а. Состояния и два класса проектов на экране ABM.]"
                "(../figures/native_abm_mixed.png)"
            )
    native_dynamics = ""
    sd_paths = [ROOT / f"results/native/sd-{case}/series.csv" for case in ("base", "demand", "shock")]
    if all(path.is_file() for path in sd_paths):
        outcomes = []
        for path in sd_paths:
            with path.open(encoding="utf-8", newline="") as stream:
                outcomes.append(fmt(list(csv.DictReader(stream))[-1]["paid"]))
        native_dynamics = (
            f"\n\nВ нативных 480-часовых прогонах AnyLogic накоплено {outcomes[0]} выплаты "
            f"в базовом сценарии, {outcomes[1]} при повышенном спросе и {outcomes[2]} при шоке. "
            "Все три ряда сверены с независимым численным решением и балансом проектов."
        )
    conclusion = f"""
# Исследование и оптимизация краудфандинговой платформы

Имитационное моделирование DES, ABM, SD и M/M/c/K

## Аннотация

В эталонном DES при 5 проектах/ч доля нарушений SLA модерации равна {a("base","sla")}%. Перераспределение каналов R2/R3 до 1/3 стоит 65 условных единиц при 62 в исходной конфигурации. На новой серии из десяти seeds оно дало {v("opt_007","sla")}% нарушений и {v("opt_007","payout_throughput")} выплат/ч. Скобки показывают 95% интервалы по независимым повторам. Применимость результата ограничена учебными параметрами и принятой моделью. Артефакты AnyLogic и подтверждения их запуска описаны в STATUS.md.

## 1. Постановка задачи

Платформа принимает проекты, модерирует, публикует, проводит платежи, обслуживает обращения и споры и выплачивает средства. Восемь ресурсов удовлетворяют спецификации в SPECIFICATION.md. R5 кратковременно обслуживает две разные операции — публикацию и зачисление. Кампания продолжается параллельно с платежами. Парето I с минимумом 500 коп. и формой 2,6 задаёт сумму отдельного платежа. Исходы и единицы выписаны в спецификации. Самостоятельные допущения включают калибровку интенсивности, распределение суммы цели и время обслуживания.

Уравнение (1) задаёт сохранение проектов: поступило = незавершённые + терминальные исходы. Уравнение (2) задаёт учёт копеек: зачислено = удержано + выплачено + возвращено. Прикладное правило остановки использует 2160 ч или 10 000 терминальных исходов. Фиксированный горизонт 2160 ч назначен сравнительным сериям.

## 2. Дискретно-событийная модель

Очередь событий хранит модельное время и стабильный порядок событий. В каждом ресурсе захват и освобождение меняют число занятых каналов. Очередь ограничена, а переполнение имеет явный исход. Платёж может сформировать отдельное обращение и вернуться на одну повторную попытку. После конца сбора расчёт ждёт всех уже зарегистрированных операций и запускает одну выплату. Проверены нулевая нагрузка, сквозной сценарий, перегрузка R3, спор и возвраты, ошибки платежа, недостижимая цель, остановка по счётчику и сброс между повторами. Измерения лежат в results/raw/des_checks.json.

![Рисунок 1. Измерения ресурсов в полном прогоне AnyLogic.](../figures/native_resource_metrics.png)

Базовый стохастический прогон AnyLogic PLE 8.9.8 с seed 2501 остановился после 10 000 завершений на 2019,397 ч. Он дал 9590 выплат, 158 технических отказов, 152 461 запись платежа и 17,53% нарушений зрелого SLA модерации. Суммарно зачислено 123 878 914 коп., из которых 122 607 557 выплачено, 855 346 возвращено и 416 011 удержано. Анализ этого прогона и выгрузки R1–R8 приведены в stages/02-des.md. Панель показывает 2D-метрики и изменение очередей в 3D. Отдельные графики времени и гистограммы доступны для каждого ресурса.

![Рисунок 1а. Ресурсы и 3D-очереди в контрольном прогоне DES.](../figures/native_des.png)

Уравнение (3) задаёт загрузку: интеграл занятых каналов, делённый на интеграл доступной мощности. Среднее число ожидающих равно площади под кривой очереди, делённой на время. Throughput равен числу соответствующих завершений, делённому на окно наблюдения. Общая загрузка взвешена по времени доступности каналов.

## 3. Узкое место, SLA и планирование мощности

В 12 конфигурациях проведено по 10 повторений. По зрелой когорте знаменатель охватывает все проекты с моментом подачи не позже конца окна минус 8 ч. Незавершённые к своему сроку включены в нарушения. Молодые незавершённые участвуют в диапазоне возможных исходов всей когорты. P95 относится к наблюдаемым решениям.

![Рисунок 2. Очереди R1–R8 в базовом прогоне.](../figures/all_resources_queue.png)

У R3 средняя загрузка {fmt(100*float(capacity["base","r3_util"]["mean"]))}%. При добавлении одного канала R3 средняя очередь изменилась на {ci(pairs["r3_3","r3_queue"])} проекта, доля нарушений на {ci(pairs["r3_3","sla"],100)} п.п., выплаты на {ci(pairs["r3_3","payout_throughput"])} проекта/ч. Один новый канал R2 дал изменение выплат {ci(pairs["r2_3","payout_throughput"])} проекта/ч. Разгрузка R3 подтверждается изменением SLA и очереди.

![Рисунок 3. Мощность R3, стоимость и показатели.](../figures/capacity.png)

Переход с двух до трёх каналов меняет суммарный throughput на {ci(knee["base","r3_3","throughput"],100,3)}%. Верхняя граница ниже правила 5%. Точка по совокупным завершениям слабо отражает улучшение состава исходов, поэтому рядом оценивается рост выплат и снижение отказов. При шести проектах/ч с тремя каналами R3 получено {a("load_1_2x","sla")}% нарушений, при семи — {a("load_1_4x","sla")}%. Подтверждённый запас в проверенной конфигурации R2=2, R3=3 составляет 20% относительно базы по критерию SLA. Между 6 и 7 точная граница не оценивалась.

![Рисунок 4. Распределение времени до наблюдаемого решения.](../figures/moderation_tail.png)

В базовом seed 2501 P95 при посещении R3 равен {fmt(segmentation["Ручная проверка","Посетил R3"]["delay_p95"])} ч, без R3 — {fmt(segmentation["Ручная проверка","Без R3"]["delay_p95"])} ч. Полная сегментация по категории, репутации, цели, ручной проверке, интенсивности и спору приведена в results/processed/cohort_segments.csv. Группы по фактическим маршрутам и спорам описательны, поскольку сформированы после моделируемых событий.

## 4. Управление параметрами и оптимизация

Фиксированный спрос 2,5/5/10 проекта в час и мощности R3 1/2/4 варьировались по одному фактору. Для R3 округление не потребовалось. Контролируются время, очереди, загрузка, SLA и выплаты. Факторный план 2⁴ с тремя повторами выявляет эффекты на выбранных крайних уровнях. Таблицы и код перечислены в experiments/OPTIMIZATION.md.

![Рисунок 5. Факторные эффекты и интервалы.](../figures/factorial.png)

![Рисунок 6. Взвешенная оценка конфигураций в эталонном поиске.](../figures/weighted_objective.png)

Требования поиска — SLA ≤5%, выплаты ≥4,4 проекта/ч, технические отказы ≤1%. В эталоне перебраны 100 конфигураций по три прогона на 168 ч. Три кандидата проверены на новых seeds 4701–4710 при 2160 ч. Вариант 65 у.е. подтверждает основной SLA. Платёжный SLA при пороге 0,5 ч даёт {v("opt_007","payment_sla")}% нарушений. Добавление пятого канала R4 увеличивает стоимость до 68 у.е. и снижает долю нарушений платёжного SLA до {v("opt_008","payment_sla")}%. Это отдельное условное решение, если организация вводит лимит нарушений и на платежи. Результаты поиска относятся к Python DES.

### 4.3. Целевая функция преподавателя

В отдельной постановке максимизируется 0,65 × throughput / 5 − 0,35 × сумма коэффициентов загрузки / 8. При тех же требованиях к SLA, выплатам и отказам введён бюджет 74 у.е. Равновзвешенная сумма восьми коэффициентов измеряет суммарную загрузку. Отдельно в таблицах сохраняется средняя загрузка, взвешенная по каналам.

На эталонной сетке оптимальная взвешенная альтернатива — R2=4, R3=3, R4=5 за 74 у.е. Независимая серия дала {ci(weighted["weighted","throughput"])} завершения/ч, сумму загрузок {ci(weighted["weighted","sum_utilization"],digits=3)} и SLA {ci(weighted["weighted","sla_failure"],100)}%. У минимального по цене варианта за 65 у.е. сумма загрузок {ci(weighted["capacity","sum_utilization"],digits=3)}. Прирост throughput мал, а снижение загрузки различимо. Нативный OptQuest использует эту же постановку.{native_summary}

## 5. Марковская модель ручной проверки

Использованы λ = {fmt(markov["lambda_offered"],4)} заявки/ч, μ = {fmt(markov["mu"],4)} заявки/ч на канал, c = 2 и K = 26. λ включает попытки входа при полной системе. В графе состояний 0 ⇄ 1 ⇄ … ⇄ 26 интенсивность перехода вверх равна λ, вниз — min(n, 2)μ. На границах нет выхода за диапазон. Уравнение (4) записывается P′ = P Q, где диагональ Q равна отрицательной сумме исходящих интенсивностей. Начальное распределение сосредоточено в нуле. Стационарная проверка использует Pₙ₊₁/Pₙ = λ /(min(n+1,c)μ).

![Рисунок 7. Динамика всех 27 вероятностей по журналу AnyLogic.](../figures/markov_native_probabilities.png)

Стационарные блокировка и очередь — {fmt(100*m["block"])}% и {fmt(m["mean_queue"])} проекта. В полной платформе на seed 2501 — {fmt(100*c["block"])}% и {fmt(c["mean_queue"])} проекта. Согласованный DES с теми же λ, μ, c и K отдельно сопоставлен на десяти длинных прогонах. Максимальная ошибка нормировки численного решения {markov["probability_error"]:.2e}. Приближение ручной проверки одним пуассоновским входом проверено сравнением, фактические возвраты и предшествующие ресурсы в него агрегированы.

## 6. Агентная модель и гетерогенность

Агент проекта хранит состояния от поступления до выплаты или завершения. Платёж хранит собственное состояние, включая поддержку. Эталонная ABM на трёх общих seeds дала те же метрики, что DES, при эквивалентных правилах. Для тяжёлых проектов среднее обслуживание R3 умножено на 2,5. Ожидаемый средний объём работы R3 при неизменном составе входа умножается на 1 + 1,5h, где h — доля тяжёлых проектов. Приоритет лёгких применяется в очереди без прерывания начатого обслуживания.

![Рисунок 8. Тяжёлые проекты и дисциплина очереди.](../figures/abm.png)

При доле 25% P95 ожидания лёгких среди начавших обслуживание — {b("heavy_25_fifo","light","p95")} ч с FIFO и {b("heavy_25_priority","light","p95")} ч с приоритетом. SLA тяжёлых в этих режимах — {b("heavy_25_fifo","heavy","sla")}% и {b("heavy_25_priority","heavy","sla")}%. Парная разность SLA тяжёлых при 25% равна {ci(agent_priority,100)} п.п. Приоритет меняет распределение ожидания при том же расчётном входном объёме работы. SLA по зрелым когортам включает заявки, до обслуживания которых очередь так и не дошла.{native_agents}

## 7. Системная динамика

Накопители — проекты на ручной обработке и в очереди, активные кампании, установленная и желаемая мощность, доверие, индекс пользователей и накопленные потоки. Мощность непрерывна и выражена в каналах R3. В уравнении (5) расход проектов R3 равен min(проекты, мощность)/1,5 ч. Доверие реагирует на поток выплат с задержкой 24 ч, индекс пользователей — 48 ч. Динамическое расширение использует сглаживание решения 8 ч и ввода мощности 16 ч. Петли R_growth и B_capacity действуют в диагностических сценариях.

![Рисунок 9. Мощность R3, шок и восстановление.](../figures/sd.png)

Горизонт 480 ч. Спрос повышается с 5 до 6,5 проекта/ч с часа 0. Шок снижает целевую мощность с двух каналов до одного с 168-го до 240-го часа. Через 24 ч после восстановления мощности очередь SD составляет {fmt(sd["shock",]["queue_24h_after_restore"])} проекта с фиксированной политикой и {fmt(sd["shock_buffer",]["queue_24h_after_restore"])} при динамической политике. DES при том же календаре физически закрывает канал сразу, SD учитывает постепенный ввод и выбытие. Согласование определяется направлением реакции и графиками, а траектории и уровень вариантов различаются. Баланс сходится с погрешностью <10⁻⁶ проекта. Уменьшение максимального шага 0,5 до 0,25 ч изменило вектор состояний не более чем на {max(float(x["grid_difference"]) for x in sd.values()):.2e} по числовой шкале его компонент.{native_dynamics}

## 8. Сопоставление и решение

Таблица 1. Представления и задачи исследованных моделей.

| Показатель | DES | ABM | SD | M/M/c/K |
|---|---|---|---|---|
| Время | События | События и состояния | Непрерывное | Непрерывное вероятностное |
| Очереди | Визиты R1–R8 | Ресурс и класс | Агрегат R3 | Число заявок в R3 |
| Гетерогенность | Атрибуты и маршруты | Индивидуальные состояния и приоритет | Средние доли и коэффициенты | Однородные заявки |
| SLA и квантили | Когорты и выборочные оценки | Когорты по классам | Средние потоки | Блокировка и средняя очередь |
| Обратные связи | При включении политики | При включении взаимодействий | Доверие и расширение мощности | Фиксированные интенсивности |
| Вычисления | Рост с числом событий | Состояния и события | Интеграция 11 переменных | 27 вероятностей |
| Практическая задача | Каналы и SLA | Ущерб низкому приоритету | Восстановление после шока | Быстрая оценка одного ресурса |

Два дополняющих вывода — приоритет заметно меняет ожидание лёгких и зрелый SLA тяжёлых, а накопители показывают, что добавление мощности после шока имеет собственный лаг. DES отдельно выявляет платежи как вторичное ограничение после разгрузки модерации.

Таблица 2. Альтернативы и стресс-тест. Основные прогоны 2160 ч, стресс-тест 504 ч, 6 повторений на вариант. P95 — до наблюдаемого решения. Отказы — технические отказы проектов. Сложность внедрения оценивается качественно по числу служб и необходимости перераспределения персонала.

{decision_table}

Системный анализ по Оптнеру приведён в этапах 3–9 по сравнительной таблице из учебника В. Н. Волковой и А. А. Денисова. Пункт 3 фиксирует цели и пороги. Пункт 4 связывает структуру ресурсов с дефектом R3 и миграцией к R4. Пункт 5 оценивает доступные изменения мощности, очередей и приоритетов. Пункты 6 и 7 перечисляют и оценивают пять вариантов. Пункт 8 выбирает правило и проверяет чувствительность к условиям. Пункт 9 задаёт пилот, критерии успеха и возврат к исходному расписанию.

Вариант 65 у.е. выбран по основному SLA при входе 5 проектов/ч. Если добавить условие не более 5% нарушений платёжного SLA, проверенный вариант стоит 68 у.е. При 6 проектах/ч верхняя граница SLA для 65 у.е. составила {fmt(100*s["redistribute"]["hi"])}%, а у варианта с двумя каналами R2 и тремя R3 — {fmt(100*s["r3_3"]["hi"])}%.

Для внедрения сначала провести пилот с R2=1, R3=3, R4=4 при сопоставимой нагрузке. Следить за зрелой долей нарушений, P95 наблюдаемых решений, нагрузкой R2, очередями R3/R4, выплатами и техническими отказами. Критерии пилота — верхняя граница интервала SLA ≤5%, технические отказы ≤1%, нижняя граница выплат ≥4,4 проекта/ч. При невыполнении пересмотреть распределение каналов. При росте нагрузки повторить испытания с вашим фактическим потоком и учесть запас каждого ресурса.

## Ограничения

Интенсивности, времена обслуживания и порог модерации 8 ч заданы для учебной платформы. Марковское приближение использует однородный стационарный поток к R3, а SD описывает усреднённые потоки и задержки. Доверительные интервалы характеризуют разброс между повторами в принятых условиях. Перед применением настройку распределений и порогов следует сверить с фактическими журналами платформы.

## Источники и воспроизведение

Исходное задание преподавателя, описание платформы и восьмиэтапное ТЗ. Карта требований сохранена в ASSIGNMENT.md. Для нумерации Оптнера использован учебник В. Н. Волковой и А. А. Денисова, «Теория систем и системный анализ», 2006. Электронная версия: https://djvu.online/file/PPG3Uguuc8h6U.

Документация AnyLogic о редакциях и ограничениях — https://www.anylogic.com/downloads/

Документация AnyLogic Engine API — https://anylogic.help/anylogic/running/engine-api.html

Сценарии и точные команды находятся в README.md. Отдельные материалы по этапам собраны в каталоге stages. Первичные измерения хранятся в results/raw. Обработанные таблицы — в results/processed. Графики воспроизводятся через analysis/capacity_results.py и analysis/compare_results.py. Сведения о статусе ALP, нативных экспериментов, 3D и библиотек собраны в STATUS.md.

## Приложение. Приёмочные материалы

В REQUIREMENTS.md указано, каким артефактом и проверкой подтверждён каждый пункт задания. В results/native хранятся журналы и ряды, полученные в AnyLogic. Файлы моделей и способ запуска каждого эксперимента перечислены в models/README.md. План выступления и двадцать ответов подготовлены в report/DEFENSE.md.

| Что проверить в AnyLogic | Контрольный признак | Путь к результатам |
|---|---|---|
| DES, основной прогон | 10 000 завершений и 9590 выплат при seed 2501. Сходятся проектный баланс и учёт копеек. | results/native/research/ |
| DES, правила остановки | Счётчик срабатывает на двух терминальных исходах. В отдельной проверке срабатывает горизонт 2160 ч. | results/native/count/ и results/native/horizon-diagnostic/ |
| Variation и OptQuest | 48 результатов Variation и 300 результатов OptQuest. Конфигурации и seeds доступны для сверки. | results/native/experiments/ |
| Markov, ручная очередь | 27 вероятностей в 241 точке и три оценки ёмкости. | results/native/markov/ |
| ABM, сравнение классов | Базовые агрегаты совпадают с DES. Групповые P95 меняются при вводе тяжёлых и приоритета. | results/processed/abm_native.csv |
| SD, три сценария | По 481 точке до 480-го часа. Моделируемый шок длится с 168-го до 240-го часа. | results/native/sd-base/, sd-demand/ и sd-shock/ |
""".strip()
    return conclusion + "\n"


def make_docx(source):
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    section.top_margin = Cm(1.9)
    section.bottom_margin = Cm(1.8)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(7)
    for h in ("Title", "Heading 1"):
        doc.styles[h].font.color.rgb = RGBColor.from_string("1E3A8A")
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("Краудфандинговая платформа · ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    lines = iter(source.splitlines())
    for line in lines:
        if line.startswith("# "):
            doc.add_heading(line[2:], 0)
        elif line.startswith("## "):
            doc.add_heading(line[3:], 1)
        elif line.startswith("### "):
            doc.add_heading(line[4:], 2)
        elif line.startswith("!["):
            name, path = re.fullmatch(r"!\[(.+)\]\((.+)\)", line).groups()
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.keep_with_next = True
            paragraph.add_run().add_picture(str((REPORT/path).resolve()), width=Cm(16.5))
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph(name, "Caption")
        elif line.startswith("|"):
            columns = [x.strip() for x in line.strip("|").split("|")]
            table = doc.add_table(rows=1, cols=len(columns))
            table.style = "Light Shading Accent 1"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
            for c, name in zip(table.rows[0].cells, columns):
                c.text = name
                for r in c.paragraphs[0].runs:
                    r.font.size = Pt(9)
            next(lines)
            for item in lines:
                if not item.startswith("|"):
                    break
                row = table.add_row()
                row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
                for c, value in zip(row.cells, item.strip("|").split("|")):
                    c.text = value.strip()
                    for r in c.paragraphs[0].runs:
                        r.font.size = Pt(9)
        elif line:
            doc.add_paragraph(line)
    doc.core_properties.title = "Исследование и оптимизация краудфандинговой платформы"
    doc.save(REPORT / "Отчёт.docx")


if __name__ == "__main__":
    REPORT.mkdir(parents=True, exist_ok=True)
    report = create_markdown()
    (REPORT / "REPORT.md").write_text(report, encoding="utf-8")
    make_docx(report)
