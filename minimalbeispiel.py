import os
from pathlib import Path

import owlready2
from owlready2 import AllDisjoint, Imp, Thing, World, sync_reasoner_pellet

owlready2.JAVA_EXE = os.environ.get("JAVA_EXE", "/opt/homebrew/opt/openjdk/bin/java")

QUANTITIES = {"Q_Pos": "Kran steht am Stempel", "Q_Place": "Werkstück liegt im Stempel"}
CHANNELS = {"IND": "Q_Pos", "MS": "Q_Pos", "WP": "Q_Place"}
RELATIONS = {
    "R_red": ("IND und MS stimmen überein", ["IND", "MS"], False),
    "R_IND": ("nach START meldet IND den Kran", ["IND"], True),
    "R_MS": ("nach START meldet MS den Kran", ["MS"], True),
    "R_WP": ("nach START meldet WP das Werkstück", ["WP"], True),
}
PROCESS_CAUSES = {
    "P_Pos": ("Kran kam nicht am Stempel an", ["Q_Pos", "Q_Place"], ["R_IND", "R_MS", "R_WP"]),
    "P_Place": ("Ablage misslungen", ["Q_Place"], ["R_WP"]),
}


def build_ontology(world: World):
    onto = world.get_ontology("http://example.org/minimal_kb.owl")
    with onto:
        class Quantity(Thing): pass
        class Channel(Thing): pass
        class Relation(Thing): pass
        class Satisfied(Relation): pass
        class Violated(Relation): pass
        AllDisjoint([Satisfied, Violated])
        class Cause(Thing): pass
        class SensorCause(Cause): pass
        class ProcessCause(Cause): pass

        class measures(Channel >> Quantity): pass
        class participatesIn(Channel >> Relation): pass
        class participatesInProcessSensitive(participatesIn): pass
        class affectsChannel(SensorCause >> Channel): pass
        class affectsQuantity(ProcessCause >> Quantity): pass
        class mayViolate(Cause >> Relation): pass
        class mustViolate(Cause >> Relation): pass
        class cannotViolate(Cause >> Relation): pass
        class refutedBy(Cause >> Relation): pass

        q = {name: Quantity(name, label=[text]) for name, text in QUANTITIES.items()}
        ch = {name: Channel(name, measures=[q[qty]]) for name, qty in CHANNELS.items()}
        for rname, (text, channels, sensitive) in RELATIONS.items():
            r = Relation(rname, label=[text])
            for c in channels:
                (ch[c].participatesInProcessSensitive if sensitive else ch[c].participatesIn).append(r)
        for c in CHANNELS:
            SensorCause(f"S_{c}", label=[f"Sensor {c} liefert falschen Wert"], affectsChannel=[ch[c]])
        for pname, (text, qtys, musts) in PROCESS_CAUSES.items():
            ProcessCause(pname, label=[text], affectsQuantity=[q[x] for x in qtys],
                         mustViolate=[onto[m] for m in musts])

        Imp(label=["C1"]).set_as_rule("affectsChannel(?h, ?c), participatesIn(?c, ?r) -> mayViolate(?h, ?r)")
        Imp(label=["C2"]).set_as_rule("affectsQuantity(?h, ?q), measures(?c, ?q), participatesInProcessSensitive(?c, ?r)"
                                      " -> mayViolate(?h, ?r)")
        Imp(label=["W1"]).set_as_rule("Violated(?r), cannotViolate(?h, ?r) -> refutedBy(?h, ?r)")
        Imp(label=["W2"]).set_as_rule("Satisfied(?r), mustViolate(?h, ?r) -> refutedBy(?h, ?r)")
    return onto


def close_world(onto, world: World) -> None:
    sync_reasoner_pellet(world, infer_property_values=True, debug=0)
    with onto:
        for c in onto.Cause.instances():
            may = list(c.mayViolate)
            c.mayViolate = []
            c.mayViolate = may
            c.cannotViolate = [r for r in onto.Relation.instances() if r not in c.mayViolate]


RUNS = {
    "Lauf 1 – IND schweigt": {"START": 1, "IND": 0, "MS": 1, "WP": 1},
    "Lauf 2 – alle schweigen": {"START": 1, "IND": 0, "MS": 0, "WP": 0},
    "Lauf 3 – nur WP schweigt": {"START": 1, "IND": 1, "MS": 1, "WP": 0},
}


def measure(bits: dict) -> dict:
    if not bits["START"]:
        return {}
    ok = {"R_red": bits["IND"] == bits["MS"], "R_IND": bits["IND"] == 1,
          "R_MS": bits["MS"] == 1, "R_WP": bits["WP"] == 1}
    return {r: "Satisfied" if v else "Violated" for r, v in ok.items()}


def diagnose(status: dict, kb: Path) -> tuple[str, list[str]]:
    world = World()
    onto = world.get_ontology(kb.as_uri()).load()
    with onto:
        for rname, st in status.items():
            onto[rname].is_a.append(onto[st])
    sync_reasoner_pellet(world, infer_property_values=True, debug=0)

    causes = sorted(onto.Cause.instances(), key=lambda c: c.name)
    why = [f"{c.name} widerlegt: " + "; ".join(
               f"{r.name} {'verletzt, kann nicht (W1)' if r in c.cannotViolate else 'erfüllt, muss (W2)'}"
               for r in sorted(c.refutedBy, key=lambda r: r.name))
           for c in causes if c.refutedBy]
    remaining = [c for c in causes if not c.refutedBy]
    if "Violated" not in status.values():
        finding = "NoFinding – kein Befund"
    elif len(remaining) == 1 and onto.SensorCause in remaining[0].is_a:
        finding = f"SensorFault({remaining[0].affectsChannel[0].name}) – {remaining[0].label[0]}"
    elif len(remaining) == 1:
        finding = f"ProcessFault({remaining[0].name}) – {remaining[0].label[0]}"
    elif remaining:
        finding = "Undecidable{" + ", ".join(c.name for c in remaining) + "} – nicht entscheidbar"
    else:
        finding = "UnknownCause – keine Ursache erklärt das Muster"
    return finding, why


def main() -> None:
    kb = Path(__file__).with_name("minimal_kb.owl")
    world = World()
    onto = build_ontology(world)
    close_world(onto, world)
    onto.save(file=str(kb))

    print("Wissen nach Abschlussannahme:")
    for c in sorted(onto.Cause.instances(), key=lambda c: c.name):
        print(f"  {c.name:8s} kann {sorted(r.name for r in c.mayViolate)}, muss {sorted(r.name for r in c.mustViolate)}")
    for name, bits in RUNS.items():
        status = measure(bits)
        finding, why = diagnose(status, kb)
        print(f"\n{name}   " + " ".join(f"{k}={v}" for k, v in bits.items()))
        print("  verletzt: " + (", ".join(sorted(r for r, s in status.items() if s == "Violated")) or "–"))
        print("  " + "\n  ".join(why))
        print(f"  → {finding}")


if __name__ == "__main__":
    main()
