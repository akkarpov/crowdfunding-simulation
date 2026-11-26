"""Собирает минимальный ALP на основе комплектного проекта Bank AnyLogic."""
import argparse
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("anylogic", type=Path)
args = parser.parse_args()
examples = args.anylogic / "plugins"
sample = next(examples.glob("com.anylogic.examples_*/bigbookmodels/Three methods/Bank/Bank.alp"))
document = ET.parse(sample)
model = document.find("Model")
main = model.find("ActiveObjectClasses/ActiveObjectClass")
experiment = model.find("Experiments/SimulationExperiment")
blocks = main.find("EmbeddedObjects")
connectors = main.find("Connectors")
template = {x.findtext("ActiveObjectClass/ClassName"): deepcopy(x) for x in blocks}
connector = deepcopy(connectors[0])
label = deepcopy(experiment.find("Shapes/Text"))

for parent, names in [
    (main, ("Charts", "Shapes")),
    (model, ("ModelResources",)),
    (experiment, ("Shapes",)),
]:
    for child in names:
        parent.remove(parent.find(child))
blocks.clear()
connectors.clear()

model.find("Name").text = "CrowdfundingSmoke"
model.find("Description").text = "Проверочный сценарий краудфандинга с двумя пожертвованиями"
model.find("JavaPackageName").text = "crowdfunding_smoke"
model.find("ModelTimeUnit").text = "Hour"
experiment.find("RandomNumberGenerationType").text = "fixedSeed"
experiment.find("SeedValue").text = "2501"
experiment.find("MaximumMemory").text = "256"
experiment.find("PresentationProperties/Title").text = "Краудфандинг · проверочный сценарий"
experiment.find("PresentationProperties/ExecutionMode").text = "virtualTime"
experiment.find("ModelTimeProperties/StopOption").text = "Stop at specified time"
experiment.find("ModelTimeProperties/FinalTime").text = "2.0"


def field(parent, key, value):
    node = parent.find(key)
    if node is None:
        node = ET.SubElement(parent, key)
    node.text = str(value)
    return node


def param(block, name, code, unit=None):
    parameters = block.find("Parameters")
    p = next((p for p in parameters if p.findtext("Name") == name), None)
    if p is None:
        p = ET.SubElement(parameters, "Parameter")
        field(p, "Name", name)
    v = field(p, "Value", "")
    v.clear()
    v.attrib["Class"] = "CodeUnitValue" if unit else "CodeValue"
    field(v, "Code", code)
    if unit:
        field(v, "Unit", unit).attrib["Class"] = "TimeUnits"


def block(kind, name, x, y, parameters=()):
    item = deepcopy(template[kind])
    blocks.append(item)
    for key, value in (("Id", 1800000000000 + len(blocks)), ("Name", name),
                       ("X", x), ("Y", y), ("Label/X", -20), ("Label/Y", -17)):
        field(item, key, value)
    for values in parameters:
        param(item, *values)
    return item


def connect(a, b):
    item = deepcopy(connector)
    connectors.append(item)
    field(item, "Id", 1800000005000 + len(connectors))
    field(item, "Name", f"flow{len(connectors)}")
    field(item, "X", int(a.findtext("X")) + 10)
    field(item, "Y", a.findtext("Y"))
    for prefix, element, port in [("Source", a, "out"), ("Target", b, "in")]:
        outer = item.find(prefix + "EmbeddedObjectReference")
        field(outer, "PackageName", "crowdfunding_smoke")
        field(outer, "ItemName", element.findtext("Name"))
        inner = item.find(prefix + "ConnectableItemReference")
        field(inner, "ClassName", element.findtext("ActiveObjectClass/ClassName"))
        field(inner, "ItemName", port)
    points = item.find("Points")
    points.clear()
    for x in [0, int(b.findtext("X")) - int(a.findtext("X")) - 20]:
        point = ET.SubElement(points, "Point")
        field(point, "X", x)
        field(point, "Y", 0)


def service(name, x, y, pool, duration):
    return block("Service", name, x, y,
                 [("delayTime", duration, "HOUR"), ("resourcePool", pool),
                  ("maximumCapacity", "false"), ("queueCapacity", "8")])


def source(name, y):
    result = block("Source", name, 80, y, [("arrivalType", "self.MANUAL")])
    for p in result.findall("Parameters/Parameter"):
        if p.findtext("Name") == "rate" and p.find("Value") is not None:
            p.remove(p.find("Value"))
    return result


field(main, "AdditionalClassCode", """
long confirmed = 0;
long held = 0;
long paid = 0;
int records = 0;
int payouts = 0;
boolean campaignActive = false;

void note(String event) {
    traceln(String.format(java.util.Locale.ROOT, "%.3f ч | %s | учтено %d | остаток %d | выплачено %d",
        time(), event, confirmed, held, paid));
}
void openCampaign() {
    campaignActive = true;
    note("кампания открыта");
    donations.inject(2);
}
void creditDonation() {
    if (!campaignActive || paid != 0 || records >= 2)
        throw new IllegalStateException("Недопустимое зачисление");
    records++;
    confirmed += 500;
    held += 500;
    note("пожертвование учтено");
    if (records == 2) {
        campaignActive = false;
        settlements.inject(1);
    }
}
void transferMoney() {
    if (++payouts != 1 || records != 2 || held != 1000 || campaignActive)
        throw new IllegalStateException("Недопустимая выплата");
    paid += held;
    held = 0;
    if (confirmed != held + paid)
        throw new IllegalStateException("Нарушен баланс");
    note("ПРОВЕРКА ПРОЙДЕНА");
    try {
        java.nio.file.Files.writeString(java.nio.file.Path.of(System.getProperty("java.io.tmpdir"),
            "crowdfunding-smoke-2501.txt"), "OK seed=2501 credited=1000 held=0 paid=1000 records=2 payouts=1");
    } catch (java.io.IOException e) {
        traceln(e.toString());
    }
}
""".strip())
field(main, "StartupCode", 'note("подача"); projects.inject(1);')

for i, resource in enumerate(["poolR1", "poolR2", "poolR5", "poolR4", "poolR8"]):
    block("ResourcePool", resource, 110 + i * 120, 320, [("capacity", "2")])

chains = [
    [source("projects", 110), service("R1", 205, 110, "poolR1", "0.10"),
     service("R2", 330, 110, "poolR2", "0.20"), service("R5Publish", 460, 110, "poolR5", "0.10"),
     block("Sink", "published", 590, 110, [("onEnter", "openCampaign();")])],
    [source("donations", 180), service("R4", 205, 180, "poolR4", "0.15"),
     service("R5Record", 330, 180, "poolR5", "0.05"),
     block("Sink", "credited", 460, 180, [("onEnter", "creditDonation();")])],
    [source("settlements", 250), service("R8", 205, 250, "poolR8", "0.10"),
     block("Sink", "completed", 330, 250, [("onEnter", "transferMoney();")])],
]
for chain in chains:
    for a, b in zip(chain, chain[1:]):
        connect(a, b)

shapes = ET.SubElement(main, "Shapes")
for i, (y, text, size) in enumerate([
    (20, "Краудфандинг · проверочный сценарий", 24),
    (60, "1. Подача, модерация, публикация", 13),
    (131, "2. Платёж и учёт двух пожертвований", 13),
    (201, "3. Одна выплата после достижения цели", 13),
    (370, "Цель: 1000 коп. · каждое пожертвование: 500 коп. · время: ч", 13),
]):
    node = deepcopy(label)
    shapes.append(node)
    for k, v in [("Id", 1800000010000 + i), ("Name", f"caption{i}"),
                 ("X", 45), ("Y", y), ("Font/Size", size), ("Text", text)]:
        field(node, k, v)

field(experiment, "BypassInitialScreen", "true")
ET.indent(document, space="  ")
out = ROOT / "models/des/CrowdfundingSmoke.alp"
out.parent.mkdir(parents=True, exist_ok=True)
document.write(out, encoding="utf-8", xml_declaration=True)
print(out)
