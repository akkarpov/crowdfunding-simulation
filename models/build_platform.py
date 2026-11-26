"""Собирает нативную DES-платформу с восемью очередями PML."""
from copy import deepcopy
import json
from pathlib import Path
import runpy

base = runpy.run_path(str(Path(__file__).with_name("build_smoke.py")))
ROOT = base["ROOT"]
doc, model, main = (base[k] for k in ("document", "model", "main"))
block, connect, field, param = (base[k] for k in ("block", "connect", "field", "param"))
ET, source, service = (base[k] for k in ("ET", "source", "service"))
blocks, connectors = (base[k] for k in ("blocks", "connectors"))
blocks.clear()
connectors.clear()

# Используем комплектные блоки передачи существующих агентов между процессами.
transfer = ET.parse(next(base["examples"].glob(
    "com.anylogic.examples_*/basicmodels/Enter and Exit/Enter and Exit.alp"
)))
for kind in ("Enter", "Exit"):
    item = deepcopy(next(el for el in transfer.iter("EmbeddedObject")
                         if el.findtext("ActiveObjectClass/ClassName") == kind))
    parameters = item.find("Parameters")
    if parameters is None:
        ET.SubElement(item, "Parameters")
    else:
        parameters.clear()
    for generic in item.findall("GenericParameterSubstitute/GenericParameterSubstituteValue/Code"):
        generic.text = "Agent"
    base["template"][kind] = item

cfg = json.loads((ROOT / "config/baseline.json").read_text(encoding="utf-8"))
field(model, "Name", "CrowdfundingPlatform")
field(model, "JavaPackageName", "crowdfunding_platform")
field(model, "Description", "Дискретно-событийная платформа краудфандинга, ресурсы R1–R8")
for key in ("DifferentialEquationsMethod",):
    field(model, key, "EULER")

p = ET.SubElement(main, "Variables")
parameters = [
    ("arrivalRate", "double", 'Double.parseDouble(System.getProperty("crowdfunding.rate","5"))', "Подача проектов, проект/ч"),
    ("r2Capacity", "int", 'Integer.getInteger("crowdfunding.r2",2)', "Каналы AI-модерации"),
    ("r3Capacity", "int", 'Integer.getInteger("crowdfunding.r3",2)', "Каналы ручной модерации"),
    ("r4Capacity", "int", 'Integer.getInteger("crowdfunding.r4",4)', "Каналы платёжного шлюза"),
    ("seed", "int", 'Integer.getInteger("crowdfunding.seed",2501)', "Начальное зерно"),
    ("diagnostic", "boolean", 'Boolean.getBoolean("crowdfunding.diagnostic")', "Проверочные ветви"),
    ("detailed", "boolean", 'Boolean.parseBoolean(System.getProperty("crowdfunding.detailed","true"))', "Интерактивная панель и подробный журнал"),
    ("projectLimit", "int", 'Integer.getInteger("crowdfunding.limit",10000)', "Предел завершённых проектов"),
]
ids = {}
for i, (name, kind, val, description) in enumerate(parameters):
    node = ET.SubElement(p, "Variable", {"Class": "Parameter"})
    ids[name] = 1820000000100 + i
    for tag, value in [("Id", ids[name]), ("Name", name), ("X", 1520 + (i%4)*160), ("Y", 895 + (i//4)*55),
                       ("Description", description), ("PublicFlag", "true"),
                       ("PresentationFlag", "false"), ("ShowLabel", "false")]:
        field(node, tag, value)
    label = ET.SubElement(node, "Label")
    field(label, "X", 0)
    field(label, "Y", -12)
    prop = ET.SubElement(node, "Properties", {"SaveInSnapshot": "true", "ModificatorType": "STATIC"})
    for tag, value in [("Type", kind), ("UnitType", "NONE"), ("SdArray", "false")]:
        field(prop, tag, value)
    dv = ET.SubElement(prop, "DefaultValue", {"Class": "CodeValue"})
    field(dv, "Code", val)

ev = ET.SubElement(ET.SubElement(main, "DynamicEvents"), "DynamicEventClass")
for k, v in [("Id", 1820000000300), ("Name", "Work"), ("X", 2180), ("Y", 1010),
             ("PublicFlag", "false"), ("PresentationFlag", "false"),
             ("ShowLabel", "false"), ("Action", "step.run();")]:
    field(ev, k, v)
elabel = ET.SubElement(ev, "Label")
field(elabel, "X", 10)
field(elabel, "Y", -12)
arg = ET.SubElement(ev, "Parameter")
field(arg, "Name", "step")
field(arg, "Type", "Runnable")

def flow(left, right):
    connect(left, right)
    item = connectors[-1]
    for side in ("Source", "Target"):
        field(item.find(side+"EmbeddedObjectReference"), "PackageName", "crowdfunding_platform")

# Схема исполнения вынесена вправо от панели. Пул технических носителей
# создаётся один раз. Каждый проект и платёж имеют независимые данные.
pool_source = source("visitCarriers", 100)
field(pool_source, "X", 1550)
pool_storage = block("Exit", "readyCarriers", 1740, 100, [("onExit", "returnCarrier(agent);")])
flow(pool_source, pool_storage)
for r, (capacity, q, mean, cost) in enumerate(cfg["resources"].values()):
    y = 205 + 82*r
    rid = "R" + str(r + 1)
    cap = {1:"r2Capacity",2:"r3Capacity",3:"r4Capacity"}.get(r,str(capacity))
    block("ResourcePool", "pool"+rid, 2220, y, [("capacity", cap)])
    entrance = block("Enter", "input"+rid, 1550, y, [("pushProtocol", "false")])
    measure_in = block("TimeMeasureStart", "start"+rid, 1690, y)
    server = service("service"+rid, 1820, y, "pool"+rid, f"serviceDuration({r})")
    param(server, "queueCapacity", str(max(1, q)))
    param(server, "onEnterDelay", f"beginService({r}, agent);")
    measure_out = block("TimeMeasureEnd", "finish"+rid, 1950, y,
                        [("startObjects", "{ start"+rid+" }")])
    out = block("Exit", "exit"+rid, 2080, y, [("onExit",f"leaveResource({r}, agent);")])
    chain = (entrance, measure_in, server, measure_out, out)
    for left, right in zip(chain, chain[1:]):
        flow(left, right)

names = ["Подача", "AI-модерация", "Ручная модерация", "Платёжный шлюз",
         "Публикация и учёт", "Поддержка", "Арбитраж", "Выплата"]
shapes = main.find("Shapes")
style = deepcopy(shapes[0])
shapes.clear()

def caption(i, x, y, text, size):
    n = deepcopy(style)
    shapes.append(n)
    for k,v in [("Id",1820000100000+i),("Name",f"caption{i}"),("X",x),("Y",y),
                ("Font/Size",size),("Text",text)]:
        field(n,k,v)
    return n


caption(10,1530,25,"Дискретно-событийная схема · вход, измерение, обслуживание, выход",20)
for i, name in enumerate(names):
    caption(i+2, 1530, 160 + 82*i, f"R{i+1} · {name}", 13)

queues = ", ".join(str(item[1]) for item in cfg["resources"].values())
means = ", ".join(str(item[2]) for item in cfg["resources"].values())
code = (ROOT/"models/des/Main.code").read_text(encoding="utf-8")
field(main, "AdditionalClassCode", f"final int[] queueLimits = {{{queues}}};\n"
      f"final double[] serviceMeans = {{{means}}};\n"+code)
field(main, "StartupCode", "startPlatform();")

simulation = base["experiment"]
field(simulation.find("PresentationProperties"), "Title", "Краудфандинг · ресурсы платформы")
field(simulation.find("ModelTimeProperties"), "FinalTime", "4.5")

experiments = model.find("Experiments")
def experiment_copy(template, name, index, horizon, options):
    ex = deepcopy(template)
    field(ex, "Id", 1820000004000+index)
    field(ex, "Name", name)
    field(ex.find("ModelTimeProperties"), "FinalTime", horizon)
    field(ex, "VmArgs", options)
    experiments.append(ex)

field(simulation, "VmArgs", "-Dcrowdfunding.case=simulation -Dcrowdfunding.diagnostic=true")
experiment_copy(simulation, "Research", 1, 2160, "-Dcrowdfunding.case=research")
experiment_copy(simulation, "CountCheck", 2, 4.5,
                "-Dcrowdfunding.case=count -Dcrowdfunding.diagnostic=true -Dcrowdfunding.limit=2")
experiment_copy(simulation, "ZeroLoad", 3, 10, "-Dcrowdfunding.case=zero -Dcrowdfunding.rate=0")
experiment_copy(simulation, "Congestion", 4, 48,
                "-Dcrowdfunding.case=congestion -Dcrowdfunding.rate=18 -Dcrowdfunding.r3=1")
field(model.find("Frame"), "Width", 1220)
field(model.find("Frame"), "Height", 760)
ET.indent(doc, space="  ")
doc.write(ROOT/"models/des/CrowdfundingPlatform.alp",encoding="utf-8",xml_declaration=True)
