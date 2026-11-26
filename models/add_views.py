"""Нативная панель DES и 3D-представление очередей."""
from copy import deepcopy
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

models = Path(__file__).resolve().parent
examples = next((Path(sys.argv[1]) / "plugins").glob("com.anylogic.examples_*"))
sample = ET.parse(next(examples.rglob("A Very Simple Model With 3D Animation.alp")))
path = models / "des/CrowdfundingPlatform.alp"
doc = ET.parse(path)
main = doc.find("Model/ActiveObjectClasses/ActiveObjectClass")
shapes = main.find("Shapes")
control = deepcopy(next(x for x in sample.iter("Control") if x.get("Type") == "Window3D"))
rectangle = deepcopy(next(x for x in sample.iter("Rectangle") if "3D" in x.findtext("DrawMode", "")))
style = deepcopy(shapes[0])
sequence = 1820000111000


def color(hexcode):
    return int("FF" + hexcode, 16) - (1 << 32)


def set_text(parent, tag, value):
    node = parent.find(tag)
    if node is None:
        node = ET.SubElement(parent, tag)
    node.text = str(value)


def shape(template, name, x, y, **props):
    global sequence
    sequence += 1
    node = deepcopy(template)
    for key, value in {"Id": sequence, "Name": name, "X": x, "Y": y, **props}.items():
        set_text(node, key, value)
    return node


def caption(name, x, y, text, size=13, tone="F8FAFC", mode="SHAPE_DRAW_2D"):
    node = shape(style, name, x, y, Text=text, Z=0, DrawMode=mode, Color=color(tone),
                 ShowLabel="false", **{"Font/Size": size})
    shapes.append(node)


def plate(name, x, y, w, h, tone):
    return shape(rectangle, name, x, y, Width=w, Height=h, Z=0, ZHeight=0,
                 DrawMode="SHAPE_DRAW_2D", FillColor=color(tone), FillMaterial="null",
                 ShowLabel="false")


bg = plate("dashboardBg", 0, 0, 1220, 720, "0F172A")
shapes.insert(0, bg)
shapes.append(plate("statisticsBg", 28, 150, 722, 411, "1E293B"))
shapes.append(plate("sceneBg", 769, 150, 423, 411, "1E293B"))
caption("heading", 32, 23, "Краудфандинг", 28)
caption("subtitle", 34, 65, "Дискретно-событийная модель · 8 ресурсов", 14, "CBD5E1")
caption("liveKpi", 34, 112, "Ожидание запуска", 13)
caption("statisticsTitle", 46, 168, "Ресурсы и очереди", 17)
caption("queueHeading", 786, 169, "Очереди в 3D", 17)
caption("sceneOrder", 786, 502, "Дальний ряд · R1–R4      Ближний ряд · R5–R8", 11, "CBD5E1")
caption("sceneLegend", 786, 529, "Высота — число заявок в очереди", 11, "CBD5E1")

columns = [46, 247, 325, 406, 509, 621]
for i, (x, value) in enumerate(zip(columns, ["Ресурс", "Очередь", "Загрузка", "Ожидание, ч", "Сервис, ч", "Отказы"])):
    caption(f"col{i}", x, 211, value, 11, "CBD5E1")
names = ["Р1 · Подача", "Р2 · AI-модерация", "Р3 · Ручная модерация", "Р4 · Платёжный шлюз",
         "Р5 · Публикация и учёт", "Р6 · Поддержка", "Р7 · Арбитраж", "Р8 · Выплата"]
for r, name in enumerate(names):
    y = 242 + 37*r
    if r % 2:
        shapes.append(plate(f"row{r}", 40, y-5, 698, 31, "26364D"))
    caption(f"resource{r}", columns[0], y, name, 11)
    for c, x in enumerate(columns[1:]):
        caption(f"value{r}_{c}", x, y, "—", 12)
    x3, y3 = 65 + 92*(r%4), 65 + 108*(r//4)
    pillar = shape(rectangle, f"pillar{r}", x3, y3, Width=55, Height=48, Z=0,
                   ZHeight=8, DrawMode="SHAPE_DRAW_3D", FillMaterial="null",
                   FillColor=color("3B82F6"), ShowLabel="false")
    shapes.append(pillar)

caption("window", 34, 591, "Интервал наблюдения начат в 0 ч", 12, "CBD5E1")
caption("balances", 34, 623, "Денежный баланс: ожидание операций", 12, "CBD5E1")
caption("carrierText", 34, 655, "Технический пул: ожидание запуска", 12, "CBD5E1")
control = shape(control, "queueWindow", 786, 206, Width=388, Height=282,
                MakeDefaultViewArea="false")
controls = main.find("Controls")
if controls is None:
    controls = ET.SubElement(main, "Controls")
controls.append(control)

field = main.find("AdditionalClassCode")
if "void refreshVisual()" in field.text:
    raise ValueError("Панель уже добавлена. Сначала запустите build_platform.py.")
columns_java = ",\n        ".join("{" + ",".join(f"value{r}_{c}" for c in range(5)) + "}" for r in range(8))
pillars_java = ",".join(f"pillar{r}" for r in range(8))
field.text += f"""

String metric(double value) {{
    return Double.isFinite(value) ? String.format(java.util.Locale.ROOT, "%.2f", value) : "—";
}}
void refreshVisual() {{
    if (!detailed || capacity == null) return;
    ShapeText[][] cells = {{
        {columns_java}
    }};
    ShapeRectangle[] pillars = {{{pillars_java}}};
    for (int i = 0; i < 8; i++) {{
        integrate(i);
        cells[i][0].setText(Integer.toString(waiting[i]));
        double u = time() > 0 ? busyArea[i] / (capacity[i]*time()) : Double.NaN;
        cells[i][1].setText(Double.isFinite(u) ? String.format(java.util.Locale.ROOT, "%.1f%%",100*u) : "—");
        cells[i][2].setText(metric(served[i]+busy[i] > 0 ? waitTotal[i] / (served[i]+busy[i]) : Double.NaN));
        cells[i][3].setText(metric(served[i] > 0 ? serviceTotal[i] / served[i] : Double.NaN));
        cells[i][4].setText(Integer.toString(refused[i]));
        pillars[i].setSize(55,48,8 + 4*waiting[i]);
    }}
    liveKpi.setText(summary());
    window.setText("Окно: 0–" + metric(time()) + " ч · завершения: " + metric(time() > 0 ? terminal/time() : Double.NaN)
        + " проекта/ч · взвешенная загрузка: " + metric(100*weightedUtilization()) + "%");
    balances.setText("Подтверждено: " + confirmed + " коп. · выплачено: " + paid + " коп. · возвращено: " + refunds + " коп.");
    carrierText.setText("Носители визитов: " + carriersCreated + " · свободно: " + freeCarriers.size());
}}
"""
ET.indent(doc, space="  ")
doc.write(path, encoding="utf-8", xml_declaration=True)
