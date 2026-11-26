"""Генерация популяционной ABM: диаграммы управляют операциями проектов и платежей."""
from copy import deepcopy
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
examples = next((Path(sys.argv[1]) / "plugins").glob("com.anylogic.examples_*"))
model_file = ET.parse(root / "des/CrowdfundingPlatform.alp")
model = model_file.find("Model")
types = model.find("ActiveObjectClasses")
main = types.find("ActiveObjectClass")
package = "crowdfunding_agents"
chart_example = ET.parse(examples / "bigbookmodels/Statecharts/Statechart for Product Lifecycle/Statechart for Product Lifecycle.alp")
templates = {x.get("Class"): x for x in chart_example.find(".//StatechartElements")
             if x.get("ParentState") == "ROOT_NODE" and x.get("Class") in {"State", "EntryPoint", "Transition"}}
transfer = ET.parse(examples / "basicmodels/Enter and Exit/Enter and Exit.alp")
base = next(x for x in transfer.findall("Model/ActiveObjectClasses/ActiveObjectClass") if x.findtext("Name") == "Box")
population = next(x for x in transfer.iter("EmbeddedObject") if x.findtext("Name") == "boxes")


def put(node, path, value):
    child = node.find(path)
    if child is None:
        child = ET.SubElement(node,path)
    child.text = str(value)
    return child


for node in model.iter("PackageName"):
    if node.text == "crowdfunding_platform":
        node.text = package
put(model,"Name","CrowdfundingAgents")
put(model,"JavaPackageName",package)
put(model,"Description","Популяционная краудфандинговая платформа со Statechart проекта и пожертвования")
put(main.find("Shapes/Text[Name='subtitle']"),"Text","Агентная модель · проекты и пожертвования")
put(main.find("Shapes/Text[Name='carrierText']"),"Text","Популяции: ожидание запуска")
shapes = main.find("Shapes")
legend = shapes.find("Text[Name='sceneLegend']")
put(legend, "Text", "Высота — очередь · R3: синие лёгкие, фиолетовые тяжёлые")
manual_light = shapes.find("Rectangle[Name='pillar2']")
manual_heavy = deepcopy(manual_light)
for key, value in {"Id": 1841999999898, "Name": "manualHeavy", "Width": 25,
                   "X": int(manual_light.findtext("X")) + 29,
                   "FillColor": 0xFF8B5CF6 - (1 << 32)}.items():
    put(manual_heavy, key, value)
put(manual_light, "Width", 25)
shapes.append(manual_heavy)
phases = deepcopy(shapes.find("Text[Name='carrierText']"))
for key, value in {"Id": 1841999999899, "Name": "phaseText", "Y": 680,
                   "Text": "Состояния проектов: ожидание запуска"}.items():
    put(phases, key, value)
shapes.append(phases)

ACTOR = """
String phase = "Idle";
Runnable nextAction;

void dispatch(String next, Runnable action) {
    if (nextAction != null) throw new IllegalStateException("Повторный переход агента");
    nextAction = action;
    if (!lifecycle.receiveMessage(next)) {
        nextAction = null;
        throw new IllegalStateException("Запрещённый переход " + phase + " → " + next);
    }
}
void entered(String state) {
    phase = state;
    Runnable action = nextAction;
    nextAction = null;
    if (action != null) action.run();
}
"""

project_edges = {
    "Idle": ("Intake",), "Intake": ("Waiting",), "Waiting": ("AI","Manual","Rejected"),
    "AI": ("Manual","Publication","Rejected"), "Manual": ("Publication","Appeal","Rejected"),
    "Appeal": ("Manual","Rejected"), "Publication": ("Funding","Rejected"),
    "Funding": ("Draining",), "Draining": ("Arbitration","Payout","Rejected"),
    "Arbitration": ("Payout","Rejected"), "Payout": ("Paid","Rejected"), "Paid": (), "Rejected": (),
}
payment_edges = {"Idle":("Gateway",),"Gateway":("Record","Support","Closed"),
                 "Record":("Support","Closed"),"Support":("Gateway","Closed"),"Closed":("Idle",)}


def actor(index,name,pop,edges):
    template = deepcopy(base)
    stem = 1841000000000 + index*10000
    put(template,"Id",stem)
    put(template,"Name",name)
    put(template,"FlowChartsUsage","ENTITY")
    put(template,"AdditionalClassCode",ACTOR)
    for tag in ("Variables","Functions","ContainerLinks","Presentation","CurrentLevel"):
        node = template.find(tag)
        if node is not None:
            template.remove(node)
    links = template.find("AgentLinks")
    if links is not None:
        for i, link in enumerate(links,1):
            put(link,"Id",stem+10+i)
        put(template,"ConnectionsId",stem+11)
    ruler = template.find("Shapes/ScaleRuler")
    if ruler is not None:
        put(ruler,"Id",stem+25)
    generic = template.find("GenericParameter")
    if generic is not None:
        put(generic,"Id",stem+20)
    types.append(template)
    chart = ET.SubElement(template,"StatechartElements")
    ids = {n:stem+100+i for i,n in enumerate(edges)}
    coords = {n:(90+i%4*190,100+i//4*105) for i,n in enumerate(edges)}
    for state in edges:
        item=deepcopy(templates["State"])
        chart.append(item)
        x,y=coords[state]
        for k,v in [("Id",ids[state]),("Name",state),("X",x),("Y",y)]:
            put(item,k,v)
        props=item.find("Properties")
        props.attrib.update(Width="120",Height="42")
        put(props,"EntryAction",f'entered("{state}");')
    entry=deepcopy(templates["EntryPoint"])
    chart.append(entry)
    for key,value in [("Id",stem+31),("Name","lifecycle"),("X",50),("Y",120)]:
        put(entry,key,value)
    entry.find("Properties").set("Target",str(ids["Idle"]))
    seq=0
    for begin,targets in edges.items():
        for end in targets:
            seq+=1
            item=deepcopy(templates["Transition"])
            chart.append(item)
            x,y=coords[begin]
            a,b=coords[end]
            for k,v in [("Id",stem+400+seq),("Name",f"transition{seq}"),("X",x+60),
                         ("Y",y+20),("ShowLabel","false"),("IconOffset",25)]:
                put(item,k,v)
            point=item.findall("Points/Point")[1]
            put(point,"X",a-x)
            put(point,"Y",b-y)
            props=item.find("Properties")
            props.attrib.update(Source=str(ids[begin]),Target=str(ids[end]),Trigger="message")
            put(props,"Action","")
            put(props,"Condition","true")
            put(props,"FilterType","satisfies")
            put(props,"SatisfiesExpression",f'"{end}".equals(msg)')
    e=deepcopy(population)
    main.find("EmbeddedObjects").append(e)
    for k,v in [("Id",stem+900),("Name",pop),("X",1600+200*index),("Y",1040),
                 ("PresentationFlag","false"),("ShowLabel","false"),
                 ("ActiveObjectClass/PackageName",package),("ActiveObjectClass/ClassName",name),
                 ("Replication/Code","0"),("InEnvironment","false")]:
        put(e,k,v)
    e.find("Parameters").clear()
    e.remove(e.find("PresentationId"))
    substitute=e.find("GenericParameterSubstitute")
    if substitute is not None:
        e.remove(substitute)


actor(1,"ProjectAgent","projectAgents",project_edges)
actor(2,"DonationAgent","donationAgents",payment_edges)
data=main.find("AdditionalClassCode")
code=data.text


def change(old,new):
    global code
    assert code.count(old)==1,old
    code=code.replace(old,new,1)


change("int pending, donations;","int pending, donations;\n    ProjectAgent lifecycle;\n    boolean heavy;")
change("int attempts;","int attempts;\n    DonationAgent lifecycle;")
change("    double serviceStart;", "    double serviceStart;\n    Project project;\n    int resource;\n    boolean started;")
change("new java.util.Random[7]","new java.util.Random[8]")
change("void startPlatform() {","""final java.util.ArrayDeque<DonationAgent> donationPool = new java.util.ArrayDeque<>();
final java.util.List<Double> lightManualWaits = new java.util.ArrayList<>();
final java.util.List<Double> heavyManualWaits = new java.util.ArrayList<>();
final double heavyShare = Double.parseDouble(System.getProperty("crowdfunding.abm.heavy","0"));
final boolean preferLight = Boolean.getBoolean("crowdfunding.abm.priority");

void step(Project p, String phase, Runnable callback) {
    create_Work(.00000001, () -> p.lifecycle.dispatch(phase,callback));
}
void step(Donation d, String phase, Runnable callback) {
    create_Work(.00000001, () -> d.lifecycle.dispatch(phase,callback));
}
double priority(Agent carrier) {
    Ticket visit = tickets.get(carrier);
    return preferLight && visit != null && visit.project != null && !visit.project.heavy ? 1 : 0;
}

void startPlatform() {""")
change("boolean offer(int r, Runnable done) {","""boolean offer(int r, Runnable done) { return offer(r,done,null); }

boolean offer(int r, Runnable done, Project project) {""")
change("tickets.put(carrier, new Ticket(time(), done));", """Ticket ticket = new Ticket(time(),done);
    ticket.project = project;
    ticket.resource = r;
    tickets.put(carrier,ticket);""")
change("    ticket.serviceStart = time();", "    ticket.serviceStart = time();\n    ticket.started = true;")
change("if (detailed) resourceWaits.get(r).add(waited);","""if (detailed) resourceWaits.get(r).add(waited);
    if (r == 2 && ticket.project != null)
        (ticket.project.heavy ? heavyManualWaits : lightManualWaits).add(waited);""")
change("double serviceDuration(int r) {\n    return diagnostic ? serviceMeans[r] * .15 : exp(serviceMeans[r], 3);\n}",
       """double serviceDuration(int r) { return serviceDuration(r,null); }
double serviceDuration(int r, Agent carrier) {
    Ticket ticket = carrier == null ? null : tickets.get(carrier);
    double multiplier = r == 2 && ticket != null && ticket.project != null && ticket.project.heavy ? 2.5 : 1;
    return diagnostic ? serviceMeans[r] * .15 * multiplier : exp(serviceMeans[r] * multiplier, 3);
}""")
change("    projects.add(p);\n    submit(p, 0, () -> { if (route == 1) manual(p, 0); else submit(p, 1, () -> ai(p)); });",
       """    projects.add(p);
    p.lifecycle = add_projectAgents();
    p.heavy = diagnostic ? route == 1 : draw(7) < heavyShare;
    step(p, "Intake", () -> step(p, "Waiting", () -> submit(p, 0, () -> {
        if (route == 1) manual(p,0);
        else step(p, "AI", () -> submit(p,1,() -> ai(p)));
    })));""")
change("if (!offer(r, done)) { technical++; finish(p, false); }","if (!offer(r, done, p)) { technical++; finish(p, false); }")
change("    submit(p, 2, () -> {","    step(p, \"Manual\", () -> submit(p, 2, () -> {")
change("            support(new SupportRequest(p, time(), () -> manual(p, 1), () -> reject(p)));",
       '            step(p, "Appeal", () -> support(new SupportRequest(p, time(), () -> manual(p, 1), () -> reject(p))));')
change("    });\n}\nvoid moderate(Project p)","    }));\n}\nvoid moderate(Project p)")
change("    submit(p, 4, () -> {","    step(p, \"Publication\", () -> submit(p, 4, () -> step(p, \"Funding\", () -> {")
change("        scheduleDonation(p);\n    });\n}\nvoid reject","        scheduleDonation(p);\n    })));\n}\nvoid reject")
change("        gateway(new Donation(p, amount, time()));","""        Donation d = new Donation(p, amount, time());
        d.lifecycle = donationPool.isEmpty() ? add_donationAgents() : donationPool.removeFirst();
        step(d, "Gateway", () -> gateway(d));""")
change("""        if (error || !offer(4, () -> credit(d))) paymentProblem(d);
""","""        if (error) paymentProblem(d);
        else step(d, "Record", () -> { if (!offer(4, () -> credit(d))) paymentProblem(d); });
""")
change("        support(new SupportRequest(d.project, time(), () -> gateway(d), () -> completeDonation(d)));",
       '        step(d, "Support", () -> support(new SupportRequest(d.project, time(),\n            () -> step(d, "Gateway", () -> gateway(d)), () -> completeDonation(d))));')
change("    d.finished = true;\n    d.project.pending--;\n    settle(d.project);","""    step(d, "Closed", () -> {
        d.finished = true;
        d.project.pending--;
        if (d.project.lifecycle.phase.equals("Draining")) settle(d.project);
        step(d, "Idle", () -> donationPool.addLast(d.lifecycle));
    });""")
change("        active--;\n        settle(p);",'        active--;\n        step(p, "Draining", () -> settle(p));')
change("        submit(p, 6, () -> {",'        step(p, "Arbitration", () -> submit(p, 6, () -> {')
change("            else payout(p);\n        });","            else payout(p);\n        }));")
change('    submit(p, 7, () -> finish(p, true));','    step(p, "Payout", () -> submit(p, 7, () -> finish(p, true)));')
change("""void finish(Project p, boolean success) {
""","""void finish(Project p, boolean success) {
    step(p, success ? "Paid" : "Rejected", () -> finishInState(p,success));
}
void finishInState(Project p, boolean success) {
""")
change('    saveOutput(prefix + "metrics.csv", metrics);','''    saveOutput(prefix + "metrics.csv", metrics);
    saveOutput(prefix + "classes.csv","class,projects,visits_r3,p95_wait_h\\n" +
        "light," + projects.stream().filter(p->!p.heavy).count() + "," + lightManualWaits.size() +
        "," + quantile(lightManualWaits,.95) + "\\nheavy," + projects.stream().filter(p->p.heavy).count() +
        "," + heavyManualWaits.size() + "," + quantile(heavyManualWaits,.95) + "\\n");''')
change('    carrierText.setText("Носители визитов: " + carriersCreated + " · свободно: " + freeCarriers.size());',
       '''    int lightQueue = 0, heavyQueue = 0;
    for (Ticket ticket : tickets.values()) {
        if (ticket.resource != 2 || ticket.started || ticket.project == null) continue;
        if (ticket.project.heavy) heavyQueue++; else lightQueue++;
    }
    pillars[2].setSize(25,48,8 + 4*lightQueue);
    manualHeavy.setSize(25,48,8 + 4*heavyQueue);
    int heavy = 0, moderating = 0, funding = 0, resolving = 0;
    for (Project project : projects) {
        if (project.heavy) heavy++;
        switch (project.lifecycle.phase) {
            case "Intake": case "Waiting": case "AI": case "Manual": case "Appeal": moderating++; break;
            case "Publication": case "Funding": case "Draining": funding++; break;
            case "Arbitration": case "Payout": resolving++; break;
        }
    }
    carrierText.setText("Проекты · лёгкие: " + (projects.size()-heavy) + " · тяжёлые: " + heavy
        + " · агенты платежей в работе: " + (donationAgents.size()-donationPool.size()));
    phaseText.setText("Состояния · подача и модерация: " + moderating + " · кампания: " + funding
        + " · спор и выплата: " + resolving + " · завершено: " + terminal);''')
data.text=code

def block_param(block, name, expr):
    params=block.find("Parameters")
    node=next((p for p in params if p.findtext("Name")==name),None)
    if node is None:
        node=ET.SubElement(params,"Parameter")
        put(node,"Name",name)
    value=put(node,"Value","")
    value.attrib["Class"]="CodeValue"
    put(value,"Code",expr)


service=main.find("EmbeddedObjects/EmbeddedObject[Name='serviceR3']")
put(service,"Parameters/Parameter[Name='delayTime']/Value/Code","serviceDuration(2,agent)")
block_param(service,"priority","priority(agent)")
block_param(service,"enablePreemption","false")

experiments=model.find("Experiments")
for ex in list(experiments):
    if ex.findtext("Name") not in ("Simulation","Research"):
        experiments.remove(ex)
sim=experiments.find("SimulationExperiment[Name='Simulation']")
research=experiments.find("SimulationExperiment[Name='Research']")
put(sim,"VmArgs","-Dcrowdfunding.case=abm_sim -Dcrowdfunding.diagnostic=true")
put(research,"VmArgs","-Dcrowdfunding.case=abm_base")
for i,(name,extras) in enumerate([("Mixed",""),("MixedPriority"," -Dcrowdfunding.abm.priority=true")],1):
    exp=deepcopy(research)
    put(exp,"Name",name)
    put(exp,"Id",1841999999900+i)
    put(exp,"VmArgs",f"-Dcrowdfunding.case=abm_{name.lower()} -Dcrowdfunding.abm.heavy=0.25{extras}")
    experiments.append(exp)
for exp in experiments:
    put(exp.find("PresentationProperties"),"Title","Краудфандинг · популяционная ABM")
ET.indent(model_file,space="  ")
model_file.write(root/"abm/CrowdfundingAgents.alp",encoding="utf-8",xml_declaration=True)
