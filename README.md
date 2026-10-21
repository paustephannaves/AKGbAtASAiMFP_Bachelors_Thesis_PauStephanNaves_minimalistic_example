# AKGbAtASAiMFP_Bachelors_Thesis_PauStephanNaves_minimalistic_example

This repository consists of the minimal example used in the above mentioned bachelor's thesis
to explain the basic functionality of the intended framework.

## Prerequisites

- **Python ≥ 3.9** (tested with 3.14)
- **owlready2** (tested with 0.51): `pip install owlready2`
- **Java ≥ 25** (tested with OpenJDK 26), required by the Pellet reasoner bundled with owlready2

## Run

    python minimalbeispiel.py

If Java is not located at `/opt/homebrew/opt/openjdk/bin/java` (Homebrew default on macOS),
set the path explicitly:

    JAVA_EXE=/path/to/java python minimalbeispiel.py

The script prints the derived knowledge and the finding for each of the three test runs,
and writes the ontology to `minimal_kb.owl` (can be opened in Protégé).
