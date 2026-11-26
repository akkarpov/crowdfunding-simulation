"""Добавление нативных экспериментов к CrowdfundingPlatform.alp."""
from copy import deepcopy
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from experiment_views import add_result_panel

install = Path(sys.argv[1])
root = Path(__file__).resolve().parent
examples = next((install/"plugins").glob("com.anylogic.examples_*"))
path = root/"des/CrowdfundingPlatform.alp"
doc = ET.parse(path)
model = doc.find("Model")
main = model.find("ActiveObjectClasses/ActiveObjectClass")
experiments = model.find("Experiments")
simulation = experiments.find("SimulationExperiment")
active = main.findtext("Id")
ids = {p.findtext("Name"): p.findtext("Id") for p in main.findall("Variables/Variable")}


def set_text(parent, key, value):
    node = parent.find(key)
    if node is None:
        node = ET.SubElement(parent,key)
    node.text = str(value)
    return node


def coded(parent, key, value):
    return set_text(ET.SubElement(parent,key,{"Class":"CodeValue"}),"Code",value)


def copy_experiment(relative, tag, code, name, index, tags_to_keep):
    template = ET.parse(examples/relative).find("Model/Experiments/"+tag)
    experiment = deepcopy(template)
    for child in list(experiment):
        if child.tag not in tags_to_keep:
            experiment.remove(child)
    experiment.attrib["ActiveObjectClassId"] = active
    set_text(experiment,"Id",1820000020200+index)
    set_text(experiment,"Name",name)
    set_text(experiment,"SeedValue",3701)
    set_text(experiment,"VmArgs","-Dcrowdfunding.detailed=false -Dcrowdfunding.case="+name.lower())
    set_text(experiment,"AfterSimulationRunCode",code)
    set_text(experiment.find("ModelTimeProperties"),"FinalTime",168)
    set_text(experiment.find("PresentationProperties"),"Title","Краудфандинг · "+name)
    rep = experiment.find("ReplicationsProperties")
    set_text(rep,"UseReplication","true")
    set_text(rep,"FixedReplicationsNumber","true")
    set_text(rep,"ReplicationPerIteration",3)
    set_text(experiment,"AllowParallelEvaluations","false")
    experiments.append(experiment)
    return experiment


for child in list(experiments):
    if child.tag in {"ParamVariationExperiment","OptimizationExperiment"} or child.findtext("Name") == "Tuning":
        experiments.remove(child)

common = {"Id","Name","ClientAreaTopLeft","CommandLineArguments","MaximumMemory",
          "RandomNumberGenerationType","SeedValue","SelectionModeForSimultaneousEvents",
          "VmArgs","LoadRootFromSnapshot","AllowParallelEvaluations","ModelTimeProperties",
          "PresentationProperties","ReplicationsProperties","CustomGeneratorCode"}
variation = copy_experiment(
    "bigbookmodels/System dynamics/New Product Diffusion - Various Experiments/New Product Diffusion - Various Experiments.alp",
    "ParamVariationExperiment", 'root.logRun("Variation");', "Variation", 1,
    common | {"UseFreeformParameters","NumberOfRuns"},
)
set_text(variation,"UseFreeformParameters","false")
set_text(variation,"NumberOfRuns",16)
for name, bounds in {
    "arrivalRate":(2.5,7.5,5), "r2Capacity":(1,3,2), "r3Capacity":(2,4,2), "r4Capacity":(3,6,3),
    "seed":2501,"diagnostic":"false","detailed":"false","projectLimit":10000,
}.items():
    p = ET.SubElement(variation,"RangeVariationParamValue")
    set_text(p,"Id",ids[name])
    if isinstance(bounds, tuple):
        set_text(p,"Type","RANGE")
        for k,v in zip(("From","To","Step"),bounds):
            coded(p,k,v)
    else:
        set_text(p,"Type","FIXED")
        coded(p,"Value",bounds)

optimization = copy_experiment(
    "basicmodels/Bass Diffusion - Phase 6/Bass Diffusion - Phase 6.alp",
    "OptimizationExperiment", 'root.logRun("OptQuest");', "OptQuest", 2,
    common | {"Objective","OptimizationEngine","ObjectiveFunctionCode"},
)
set_text(optimization,"ObjectiveFunctionCode","root.optimizationScore()")
set_text(optimization,"Objective","MAXIMIZE")
set_text(optimization,"OptimizationEngine","OPTQUEST")
set_text(optimization.find("ModelTimeProperties"),"IterationCount",100)
for name, bounds in {"arrivalRate":5,"r2Capacity":(1,4),"r3Capacity":(2,6),"r4Capacity":(3,7),
                     "seed":2501,"diagnostic":"false","detailed":"false","projectLimit":10000}.items():
    p = ET.SubElement(optimization,"Parameter")
    set_text(p,"Id",ids[name])
    if isinstance(bounds, tuple):
        set_text(p,"Type","DISCRETE")
        for key,value in zip(("Min","Max","Step"),(*bounds,1)):
            coded(p,key,value)
    else:
        set_text(p,"Type","FIXED")
        coded(p,"Value",bounds)
for expr, kind, bound in [("root.moderationFailure()","LESS_OR_EQUAL",.05),
                          ("root.payoutRate()","MORE_OR_EQUAL",4.4),
                          ("root.technicalFailure()","LESS_OR_EQUAL",.01),
                          ("root.cost()","LESS_OR_EQUAL",74)]:
    p = ET.SubElement(optimization,"Requirement")
    for key,value in [("Enabled","true"),("Expression",expr),("Type",kind),("Bound",bound)]:
        set_text(p,key,value)

# Простая модель с двумя управляющими элементами до создания root.
# Каждое изменение записывается в настройки того же локального процесса эксперимента.
tuning = deepcopy(simulation)
set_text(tuning,"Id",1820000020210)
set_text(tuning,"Name","Tuning")
set_text(tuning,"VmArgs","-Dcrowdfunding.case=tuning")
set_text(tuning,"BypassInitialScreen","false")
set_text(tuning,"AfterSimulationRunCode",'root.logRun("Tuning");')
set_text(tuning.find("ModelTimeProperties"),"FinalTime",168)
set_text(tuning.find("PresentationProperties"),"Title","Краудфандинг · управление входом и R3")
screen = ET.SubElement(tuning,"Shapes")
style = deepcopy(main.find("Shapes/Text"))
for idx,(text,y,size) in enumerate([
    ("Настройка эксперимента",35,24),
    ("Интенсивность поступления проектов, проектов/ч",120,14),
    ("Каналы ручной модерации R3",240,14),
    ("Запустите расчёт кнопкой ▶ внизу окна после выбора значений.",370,12),
]):
    label = deepcopy(style)
    screen.append(label)
    for key,value in [("Id",1820000020300+idx),("Name",f"tuningLabel{idx}"),("X",56),("Y",y),
                       ("Text",text),("Font/Size",size),("ShowLabel","false")]:
        set_text(label,key,value)
control_model=ET.parse(examples/"bigbookmodels/Controls/Slider Linked To Parameter/Slider Linked To Parameter.alp")
slider_template=next(x for x in control_model.iter("Control") if x.get("Type")=="Slider")
controls=ET.SubElement(tuning,"Controls")
for i,(name,y,minimum,maximum,initial,action) in enumerate([
    ("arrivalSlider",155,2.5,10,5,
     'System.setProperty("crowdfunding.rate",String.valueOf(Math.round(arrivalSlider.getValue()*10)/10.0));'),
    ("capacitySlider",275,1,4,2,
     'System.setProperty("crowdfunding.r3",String.valueOf((int)Math.round(capacitySlider.getValue())));'),
]):
    ctl=deepcopy(slider_template)
    controls.append(ctl)
    for key,val in [("Id",1820000020350+i),("Name",name),("X",56),("Y",y)]:
        set_text(ctl,key,val)
    basic=ctl.find("BasicProperties")
    basic.attrib.update(Width="490",Height="52")
    set_text(basic,"ActionCode",action)
    ext=ctl.find("ExtendedProperties")
    for key,value in [("DefaultValueCode",initial),("MinValue",minimum),("MaxValue",maximum),("LinkTo","false")]:
        set_text(ext,key,value)
    ext.remove(ext.find("Link"))
experiments.append(tuning)

add_result_panel(variation, style, optimize=False)
add_result_panel(optimization, style, optimize=True)

ET.indent(doc,space="  ")
doc.write(path,encoding="utf-8",xml_declaration=True)
