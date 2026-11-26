"""Сборка ALP для марковских уравнений и системной динамики."""
import argparse
from copy import deepcopy
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "models/des/CrowdfundingSmoke.alp"
HOUR = 4


def put(node, name, value):
    entry = node.find(name)
    if entry is None:
        entry = ET.SubElement(node, name)
    entry.text = str(value)
    return entry


def chart_layout(main, template, groups):
    shapes = main.find("Shapes")
    palette = ["2563EB","7C3AED","059669","9A3412","0E7490",
               "A21CAF","DC2626","475569","4338CA"]
    ids = 1810000030000
    lines = []
    values = []
    scales = []

    def base_shape(tag,name,x,y):
        nonlocal ids
        ids += 1
        node = ET.SubElement(shapes,tag) if tag != "Text" else deepcopy(template)
        if tag == "Text":
            shapes.append(node)
        for key,value in [("Id",ids),("Name",name),("X",x),("Y",y),("PublicFlag","true"),
                          ("PresentationFlag","true"),("ShowLabel","false"),("DrawMode","SHAPE_DRAW_2D"),
                          ("EmbeddedIcon","false"),("Z",0)]:
            put(node,key,value)
        label = node.find("Label")
        if label is None:
            label = ET.SubElement(node,"Label")
        put(label,"X",0)
        put(label,"Y",0)
        return node

    def caption(name,x,y,value,size=12,color=-15524594):
        node=base_shape("Text",name,x,y)
        put(node,"Text",value)
        put(node,"Font/Size",size)
        put(node,"Color",color)

    def line(name,x,y,tone,points,width=1.8):
        node=base_shape("Polyline",name,x,y)
        for key,value in [("ZHeight",0),("LineWidth",width),("LineColor",tone),
                          ("LineMaterial","null"),("LineStyle","SOLID"),
                          ("BeginArrowSize",1),("BeginArrowStyle",0),("EndArrowSize",1),
                          ("EndArrowStyle",0),("FillMaterial","null"),("Closed","false")]:
            put(node,key,value)
        nodes=ET.SubElement(node,"Points")
        for x1,y1 in points:
            pt=ET.SubElement(nodes,"Point")
            put(pt,"X",x1)
            put(pt,"Y",y1)
            put(pt,"Z",0)

    for group,(header,names,max_y) in enumerate(groups):
        top=116+203*group
        caption(f"panel{group}",45,top-27,header,15)
        caption(f"origin{group}",47,top+140,"0",10)
        caption(f"max{group}",44,top-5,str(max_y).replace(".",","),10)
        line(f"axis{group}",84,top+140,-10130820,[(0,-140),(0,0),(710,0)])
        caption(f"axisTime{group}",365,top+149,"Модельное время, ч",10)
        caption(f"left{group}",84,top+146,"0",10)
        caption(f"right{group}",773,top+146,"t",10)
        for i,(var,label) in enumerate(names):
            index=len(values)
            values.append(var)
            tone=int("FF"+palette[i],16)-(1<<32)
            caption(f"leg{index}",825+103*(i//5),top+25*(i%5),label,11,tone)
            name = f"curve{index}"
            line(name,84,top+140,tone,[(0,0),(0,0)])
            lines.append(name)
            scales.append(max_y)
    caption("currentTime",44,725,"Начало расчёта",12)
    return lines, values, scales


def build(name, title, horizon, variables, code, check, groups):
    doc = ET.parse(SMOKE)
    model = doc.find("Model")
    main = model.find("ActiveObjectClasses/ActiveObjectClass")
    simulation = model.find("Experiments/SimulationExperiment")
    put(model, "Name", name)
    put(model, "JavaPackageName", name.lower())
    put(model, "Description", title)
    for tag in ["RequiredLibraryReference"]:
        model.remove(model.find(tag))
    for tag in ["Connectors", "EmbeddedObjects"]:
        main.remove(main.find(tag))
    put(model, "FixedTimeStep", "0.001")
    put(model.find("Frame"), "Width", 1060)
    put(model.find("Frame"), "Height", 760)
    put(simulation.find("PresentationProperties"), "Title", title)
    template = deepcopy(main.find("Shapes/Text"))
    main.find("Shapes").clear()
    for index, (content, size) in enumerate([(title, 22),
            ("Шаг интегрирования 0,001 ч · данные сохраняются в конце расчёта", 13)]):
        label = deepcopy(template)
        main.find("Shapes").append(label)
        for key, value in [("Id", 1810000000100 + index), ("Name", f"label{index}"),
                           ("X", 40), ("Y", 16 + 30 * index), ("Font/Size", size), ("Text", content)]:
            put(label, key, value)

    for exp, limit in [(simulation, HOUR + .25)]:
        put(exp.find("ModelTimeProperties"), "FinalTime", limit)
    long_exp = deepcopy(simulation)
    put(long_exp, "Id", 1810000000200)
    put(long_exp, "Name", "Research")
    put(long_exp.find("ModelTimeProperties"), "FinalTime", horizon)
    model.find("Experiments").append(long_exp)
    if name == "PlatformDynamics":
        for scenario,title1 in enumerate(("Research","RisingDemand","CapacityShock","Adaptive","Endogenous")):
            exp = long_exp if scenario == 0 else deepcopy(long_exp)
            put(exp,"Name",title1)
            put(exp,"Id",1810000000200+scenario)
            put(exp,"VmArgs",f"-Dcrowdfunding.sd.scenario={scenario}")
            if scenario:
                model.find("Experiments").append(exp)

    lines, values, scales = chart_layout(main, template, groups)

    put(main, "AdditionalClassCode", code)
    put(main, "StartupCode", f"create_Audit({HOUR}); create_Track(0.000001); create_FinalSample(getEngine().getStopTime() - .00001);")
    base = ET.SubElement(main, "Variables")
    for index, (var, unit, initial, expr) in enumerate(variables):
        v = ET.SubElement(base, "Variable", {"Class": "StockVariable"})
        for key, value in [("Id", 1810000010000 + index), ("Name", var), ("Unit", unit),
                           ("X", 1220 + index % 6 * 122), ("Y", 105 + index // 6 * 65),
                           ("PublicFlag", "true"), ("PresentationFlag", "false"), ("ShowLabel", "true")]:
            put(v, key, value)
        offset = ET.SubElement(v, "Label")
        put(offset, "X", -10)
        put(offset, "Y", 14)
        prop = ET.SubElement(v, "Properties", {"Array": "false"})
        for key, value in [("EquationStyle", "custom"), ("Width", 20), ("Height", 20),
                           ("Expression", expr), ("InitialValue", initial), ("Color", -8580535)]:
            put(prop, key, value)
    ev = ET.SubElement(ET.SubElement(main, "DynamicEvents"), "DynamicEventClass")
    for key, value in [("Id", 1810000020000), ("Name", "Audit"), ("X", 1200), ("Y", 500),
                       ("PublicFlag", "false"), ("PresentationFlag", "true"),
                       ("ShowLabel", "false"), ("Action", "audit();")]:
        put(ev, key, value)
    label = ET.SubElement(ev, "Label")
    put(label, "X", 0)
    put(label, "Y", 0)
    for index, action in enumerate(("record(true);","record(false);"),1):
        event = deepcopy(ev)
        for k,v in {"Id":1810000020000+index,"Name":("Track","FinalSample")[index-1],
                    "X":1200+index*110,"Action":action}.items():
            put(event,k,v)
        main.find("DynamicEvents").append(event)

    series_vars = ",".join(v[0] for v in variables)
    series_header = ",".join(v[0] for v in variables)
    state_header = "scenario" if name == "PlatformDynamics" else "model"
    identity = 'String.valueOf(scenario)' if name == "PlatformDynamics" else '"markov"'
    chart_code = f"""
int sampleIndex;
ShapePolyLine[] paths;
final StringBuilder runSeries = new StringBuilder("hour,{state_header},{series_header}\\n");
void record(boolean scheduleNext) {{
    if (paths == null) {{
        paths = new ShapePolyLine[] {{{','.join(lines)}}};
        ShapeText[] rightTicks = {{{','.join(f"right{i}" for i in range(len(groups)))}}};
        for (ShapeText tick : rightTicks)
            tick.setText(String.format(java.util.Locale.ROOT,"%.2f",getEngine().getStopTime()));
    }}
    double[] plotted = {{{','.join(values)}}};
    double[] maxY = {{{','.join(str(y) for y in scales)}}};
    double horizon = getEngine().getStopTime();
    double x = 710 * time() / horizon;
    for (int i = 0; i < paths.length; i++) {{
        double y = -140 * Math.min(1, Math.max(0, plotted[i]/maxY[i]));
        ShapePolyLine curve = paths[i];
        curve.setNPoints(Math.max(2, sampleIndex + 1));
        curve.setPoint(sampleIndex,x,y);
        if (sampleIndex == 0) curve.setPoint(1,x,y);
    }}
    sampleIndex++;
    currentTime.setText(String.format(java.util.Locale.ROOT,"Модельное время: %.2f / %.2f ч",time(),horizon));
    double[] current = {{{series_vars}}};
    runSeries.append(time()).append(',').append({identity});
    for (double value : current) runSeries.append(',').append(value);
    runSeries.append('\\n');
    if (scheduleNext) {{
        if (time()+1 < horizon-.00002) create_Track(1);
    }} else {{
        try {{
            java.nio.file.Files.writeString(java.nio.file.Path.of(System.getProperty("java.io.tmpdir"),
                "crowdfunding-series-{name.lower()}-" + {identity} + ".csv"),runSeries.toString());
        }} catch (java.io.IOException e) {{ throw new RuntimeException(e); }}
    }}
}}
"""
    put(main, "AdditionalClassCode", code + "\n" + check + chart_code)
    folder = ROOT / ("models/markov" if name == "ManualQueueMarkov" else "models/sd")
    folder.mkdir(parents=True, exist_ok=True)
    ET.indent(doc, space="  ")
    xml = ET.tostring(doc.getroot(), encoding="utf-8", xml_declaration=True)
    xml = re.sub(rb"(<(?:Inputs|Parameters)>)[ \t]+(?=\n)", rb"\1", xml)
    (folder / (name + ".alp")).write_bytes(xml)


def audit(suffix, expr, message):
    return f"""
void audit() {{
    String value = {expr};
    traceln("{message} " + value);
    try {{
        java.nio.file.Files.writeString(java.nio.file.Path.of(System.getProperty("java.io.tmpdir"),
            "crowdfunding-{suffix}.txt"), value);
    }} catch (java.io.IOException e) {{
        throw new RuntimeException(e);
    }}
}}
"""


def markov():
    rate = json.loads((ROOT / "results/raw/markov.json").read_text(encoding="utf8"))["lambda_offered"]
    states = list(range(27))
    variables = []
    for n in states:
        terms = []
        if n > 0:
            terms.append(f"lambda * p{n-1}")
        if n < 26:
            terms.append(f"{min(n+1,2)} * mu * p{n+1}")
        exits = ["lambda"] if n < 26 else []
        if n:
            exits.append(f"{min(n,2)} * mu")
        expr = " + ".join(terms) + f" - ({' + '.join(exits)}) * p{n}"
        variables.append((f"p{n}", "1", int(n == 0), expr))
    code = f"final double lambda = {rate};\nfinal double mu = 2.0 / 3;"
    guard = " + ".join(f"p{i}" for i in states)
    check = audit("markov", f'\"time=\" + time() + \" sum=\" + ({guard}) + \" p0=\" + p0 + \" p26=\" + p26',
                  "Контроль вероятностей")
    code += """
void optimizeCapacity() {
    StringBuilder data = new StringBuilder("channels,cost,blocking\\n");
    double best = Double.POSITIVE_INFINITY;
    int chosen = 0;
    for (int c = 1; c <= 3; c++) {
        double weight = 1, mass = 1;
        for (int n = 1; n <= c+24; n++) {
            weight *= lambda/(Math.min(n,c)*mu);
            mass += weight;
        }
        double blocked = weight/mass;
        if (blocked < best) { best = blocked; chosen = c; }
        data.append(c).append(',').append(5*c).append(',').append(blocked).append('\\n');
    }
    traceln("Выбрано каналов: " + chosen + ", блокировка: " + best);
    try {
        java.nio.file.Files.writeString(java.nio.file.Path.of(System.getProperty("java.io.tmpdir"),
            "crowdfunding-markov-optimization.csv"),data.toString());
    } catch (java.io.IOException e) { throw new RuntimeException(e); }
}
"""
    check = check.replace("void audit() {", "void audit() { optimizeCapacity();")
    groups = [(f"Состояния {i*9}–{i*9+8}",[(f"p{n}",f"n={n}") for n in range(i*9,i*9+9)],x)
              for i,x in enumerate((1,.16,.16))]
    build("ManualQueueMarkov", "Ручная модерация · M/M/2/26", 240, variables, code, check, groups)


def sd():
    calibration = json.loads((ROOT / "results/raw/sd_calibration.json").read_text(encoding="utf8"))
    initial = [
        ("manual", "проект", 0, "accepted() - processed()"),
        ("campaigns", "проект", 0, "publishedRate() - closed()"),
        ("capacity", "канал R3", 2, "(desired - capacity) / 16"),
        ("desired", "канал R3", 2, "(targetCapacity() - desired) / 8"),
        ("trust", "1", 0, "(paidRate() / 5 - trust) / 24"),
        ("usersIndex", "1", 0, "(trust - usersIndex) / 48"),
        ("arrivals", "проект", 0, "inputRate()"),
        ("paid", "проект", 0, "paidRate()"),
        ("other", "проект", 0, "refused() + closed() - paidRate()"),
        ("published", "проект", 0, "publishedRate()"),
    ]
    code = f"""
// 0 — база, 1 — спрос 6,5, 2 — шок, 3 — шок и масштабирование, 4 — рост с обратными связями.
int scenario = Integer.getInteger("crowdfunding.sd.scenario", 0);
final double manualShare = {calibration["manual_offers"]};
final double publicationShare = {calibration["publish_fraction"]};
final double campaignMean = {calibration["campaign_hours"]};
final double paidShare = {calibration["paid_fraction"]};
final double manualMean = {calibration["service_hours"]};

double inputRate() {{ return (scenario == 1 ? 6.5 : 5) * (1 + (scenario == 4 ? 0.15 * usersIndex : 0)); }}
double processed() {{ return min(manual, capacity) / manualMean; }}
double accepted() {{ return min(manualShare * inputRate(), processed() + max(capacity + 24 - manual, 0) / 0.75); }}
double direct() {{ return inputRate() * (1 - manualShare); }}
double publishedRate() {{ return publicationShare * (processed() + direct()); }}
double closed() {{ return campaigns / campaignMean; }}
double paidRate() {{ return paidShare * closed(); }}
double refused() {{ return inputRate() - accepted() - direct() + (1 - publicationShare) * (processed() + direct()); }}
double targetCapacity() {{
    double external = ((scenario == 2 || scenario == 3) && time() >= 168 && time() < 240) ? 1 : 2;
    return external + (scenario >= 3 ? 0.20 * max(manual - capacity - 2, 0) : 0);
}}
""".strip()
    check = audit("sd", '"time=" + time() + " arrivals=" + arrivals + " balance=" + (manual + campaigns + paid + other - arrivals)',
                  "Контроль баланса")
    groups = [
        ("Поток проектов", [("manual","R3"),("campaigns","Кампании")], 105),
        ("Мощность и адаптация", [("capacity","Каналы"),("desired","Цель")], 8),
        ("Обратная связь спроса", [("trust","Доверие"),("usersIndex","Пользователи")], 1.5),
    ]
    build("PlatformDynamics", "Платформа · накопители и обратные связи", 480, initial, code, check, groups)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("markov", "sd", "all"), default="all")
    selection = parser.parse_args().model
    if selection in ("markov", "all"):
        markov()
    if selection in ("sd", "all"):
        sd()
