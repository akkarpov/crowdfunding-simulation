"""Представление фактических результатов экспериментов AnyLogic."""
from copy import deepcopy
import xml.etree.ElementTree as ET


def field(node, path, value):
    child = node.find(path)
    if child is None:
        child = ET.SubElement(node, path)
    child.text = str(value)
    return child


def add_result_panel(experiment, text_template, optimize):
    presentation = ET.SubElement(experiment, "Presentation")
    serial = 1822500100000 if optimize else 1822500200000

    def form(tag, name, x, y):
        nonlocal serial
        serial += 1
        shape = deepcopy(text_template) if tag == "Text" else ET.Element(tag)
        presentation.append(shape)
        for key, val in {
            "Id": serial, "Name": name, "X": x, "Y": y, "Z": 0,
            "DrawMode": "SHAPE_DRAW_2D", "PublicFlag": "true",
            "PresentationFlag": "true", "ShowLabel": "false",
        }.items():
            field(shape, key, val)
        label = shape.find("Label")
        if label is None:
            label = ET.SubElement(shape, "Label")
        field(label, "X", 0)
        field(label, "Y", 0)
        return shape

    def text(name, x, y, value, size=13, tone=-14606047):
        shape = form("Text", name, x, y)
        field(shape, "Text", value)
        field(shape, "Font/Size", size)
        field(shape, "Color", tone)

    def line(name, x, y, points, tone, width=1):
        shape = form("Polyline", name, x, y)
        for key, val in {
            "ZHeight": 0, "LineWidth": width, "LineColor": tone,
            "LineMaterial": "null", "LineStyle": "SOLID",
            "BeginArrowSize": 1, "BeginArrowStyle": 0,
            "EndArrowSize": 1, "EndArrowStyle": 0, "FillMaterial": "null",
            "Closed": "false",
        }.items():
            field(shape, key, val)
        children = ET.SubElement(shape, "Points")
        for px, py in points:
            node = ET.SubElement(children, "Point")
            field(node, "X", px)
            field(node, "Y", py)
            field(node, "Z", 0)

    text("panelTitle", 42, 38, "Оптимизация OptQuest" if optimize else "Варьирование параметров", 28)
    text("panelProgress", 42, 86, "Ожидание запуска", 14)
    if optimize:
        text("panelSection", 42, 133, "Лучшие допустимые решения", 17)
        headers = ("R2", "R3", "R4", "Выплаты/ч", "SLA, %", "Цель", "Цена")
        positions = (42, 104, 170, 235, 350, 447, 540)
        rows = 10
        text("graphTitle", 680, 133, "Сходимость допустимого решения", 17)
        line("graphAxis", 680, 515, [(0, -320), (0, 0), (467, 0)], -9404273)
        for tick in range(5):
            y = 515 - 80*tick
            text(f"valueTick{tick}", 642, y-9, f"{.2*tick:.1f}".replace(".", ","), 11)
            line(f"guide{tick}", 680, y, [(0, 0), (467, 0)], -2169362)
        for tick in range(5):
            text(f"stepTick{tick}", 673 + 115*tick, 529, str(25*tick), 11)
        text("axisTitle", 1030, 554, "Итерация", 11)
        line("convergence", 680, 515, [(0, 0)]*101, -14326805, 2)
    else:
        text("panelSection", 42, 133, "Среднее трёх репликаций по комбинации", 17)
        headers = ("Вход/ч", "R2", "R3", "R4", "Заверш./ч", "Выплаты/ч", "Очереди", "Загрузка, %", "SLA, %", "P95, ч")
        positions = (42, 143, 213, 283, 363, 517, 668, 794, 946, 1081)
        rows = 16
    for i, (x, name) in enumerate(zip(positions, headers, strict=True)):
        text(f"panelHead{i}", x, 176, name, 12)
    for row in range(rows):
        y = 207 + 29*row
        if row % 2:
            line(f"rule{row}", 35, y-5,
                 [(0, 0), (550 if optimize else 1125, 0)], -2169362)
        for column, x in enumerate(positions):
            text(f"panel_{row}_{column}", x, y, "—", 12)

    cells = ",".join("{" + ",".join(f"panel_{row}_{col}" for col in range(len(headers))) + "}"
                     for row in range(rows))
    name = "OptQuest" if optimize else "Variation"
    field(experiment, "BeforeEachExperimentRunCode", "resetResultsPanel();")
    field(experiment, "AfterSimulationRunCode", f'recordTrial(root.logRun("{name}"));')
    field(experiment, "AdditionalClassCode", f"""
int trialsCaptured;
int iteration;
{"boolean panelHasObjectivePoint;" if optimize else ""}
double[] pendingTotals = new double[11];
final java.util.List<double[]> resultRows = new java.util.ArrayList<>();
String number(double value, int digits) {{
    return String.format(java.util.Locale.forLanguageTag("ru"), "%." + digits + "f", value);
}}
ShapeText[][] resultCells() {{ return new ShapeText[][] {{{cells}}}; }}
void resetResultsPanel() {{
    trialsCaptured = 0;
    iteration = 0;
    java.util.Arrays.fill(pendingTotals,0);
    resultRows.clear();
    for (ShapeText[] row : resultCells()) for (ShapeText cell : row) cell.setText("—");
    panelProgress.setText("Ожидание запуска");
    {"panelHasObjectivePoint = false; for (int i = 0; i < 101; i++) convergence.setPoint(i,0,0);" if optimize else ""}
}}
void recordTrial(String[] row) {{
    trialsCaptured++;
    for (int i = 0; i < pendingTotals.length; i++) pendingTotals[i] += Double.parseDouble(row[i+7]);
    panelProgress.setText("Репликаций: " + trialsCaptured + " · завершённых итераций: " + (trialsCaptured / 3));
    if (trialsCaptured % 3 != 0) return;
    iteration++;
    double[] data = new double[15];
    for (int i = 0; i < 4; i++) data[i] = Double.parseDouble(row[i+3]);
    for (int i = 0; i < pendingTotals.length; i++) data[i+4] = pendingTotals[i]/3;
    java.util.Arrays.fill(pendingTotals,0);
    {'''if (data[10] <= .05 && data[5] >= 4.4 && data[11] <= .01 && data[14] <= 74) {
        resultRows.add(data);
        resultRows.sort(java.util.Comparator.comparingDouble((double[] d) -> d[13]).reversed());
    }
    if (!resultRows.isEmpty()) {
        double x = 460 * Math.min(iteration, 100) / 100.0;
        double y = -400 * Math.max(0, Math.min(.8, resultRows.get(0)[13]));
        int start = panelHasObjectivePoint ? Math.min(iteration,100) : 0;
        for (int i = start; i < 101; i++) convergence.setPoint(i,x,y);
        panelHasObjectivePoint = true;
    }''' if optimize else "resultRows.add(data);"}
    ShapeText[][] cells = resultCells();
    for (int r = 0; r < Math.min(cells.length,resultRows.size()); r++) {{
        double[] d = resultRows.get(r);
        String[] values = {{{'''number(d[1],0),number(d[2],0),number(d[3],0),number(d[5],3),number(100*d[10],2),
            number(d[13],4),number(d[14],0)''' if optimize else '''number(d[0],1),number(d[1],0),number(d[2],0),
            number(d[3],0),number(d[4],3),number(d[5],3),number(d[7],2),number(100*d[8],1),
            number(100*d[10],2),number(d[12],2)'''}}};
        for (int c = 0; c < values.length; c++) cells[r][c].setText(values[c]);
    }}
}}
""")
