#!/usr/bin/env python3
"""Field router: rank Nature subject fields by seed-term matching.

Usage: route_field.py TEXTFILE [--top N]
Prints a ranked list "1. <Field> (score=N)"; the first line is the
best guess. Overlay term lists (references/overlays/<Field>.md) add
weight when present.
"""

import re
import sys
from collections import Counter
from pathlib import Path

SEEDS = {
    "Agriculture": ["crop", "soil", "yield", "cultivar", "fertilizer", "irrigation", "harvest", "agronomic"],
    "Anatomy": ["anatomical", "cadaver", "morphology", "histological section", "dissection", "organ structure"],
    "Astronomy and planetary science": ["galaxy", "stellar", "exoplanet", "redshift", "telescope", "supernova", "cosmological", "light curve", "magnitude"],
    "Biochemistry": ["enzyme", "protein", "substrate", "catalysis", "metabolite", "phosphorylation", "assay", "kinetic", "amino acid"],
    "Biogeochemistry": ["carbon cycle", "nutrient cycling", "soil carbon", "decomposition", "biogeochemical", "mineralization"],
    "Biological techniques": ["protocol", "assay", "imaging method", "staining", "microscopy technique", "workflow", "sample preparation"],
    "Biomarkers": ["biomarker", "diagnostic marker", "prognostic marker", "sensitivity and specificity", "roc curve", "cutoff"],
    "Biophysics": ["force spectroscopy", "single-molecule", "membrane potential", "fluorescence lifetime", "molecular dynamics", "biophysical"],
    "Biotechnology": ["fermentation", "bioreactor", "recombinant", "bioprocess", "genetic engineering", "crispr", "expression system"],
    "Business and industry": ["market", "firm", "industry", "commercialization", "supply chain", "revenue", "entrepreneurship"],
    "Cancer": ["tumor", "carcinoma", "oncogene", "metastasis", "apoptosis", "chemotherapy", "malignant", "cancer", "tumour"],
    "Cardiology": ["cardiac", "heart", "myocardial", "arrhythmia", "ejection fraction", "coronary", "cardiovascular"],
    "Cell biology": ["organelle", "mitochondria", "cytoskeleton", "cell cycle", "vesicle", "endocytosis", "nucleus", "cytoplasm"],
    "Chemical biology": ["probe", "ligand", "small molecule", "chemical biology", "bioorthogonal", "labeling", "inhibitor"],
    "Chemistry": ["synthesis", "reaction", "catalyst", "yield", "spectroscopy", "compound", "moiety", "stoichiometry", "solvent"],
    "Climate sciences": ["climate", "warming", "precipitation", "emission scenario", "cmip", "temperature anomaly", "greenhouse"],
    "Computational biology and bioinformatics": ["bioinformatics", "genome-wide", "sequencing reads", "alignment", "phylogenetic", "pipeline", "annotation", "gwas"],
    "Developing world": ["low-income", "developing countries", "resource-limited", "global health", "poverty"],
    "Developmental biology": ["embryo", "morphogenesis", "differentiation", "gastrulation", "developmental", "lineage"],
    "Diseases": ["disease", "pathology", "syndrome", "clinical", "patient", "diagnosis", "etiology", "morbidity"],
    "Drug discovery": ["drug", "ic50", "pharmacokinetics", "lead compound", "screening", "therapeutic", "dose", "potency"],
    "Ecology": ["ecosystem", "species richness", "biodiversity", "habitat", "population dynamics", "community", "predation"],
    "Endocrinology": ["hormone", "insulin", "thyroid", "endocrine", "glucose", "secretion", "receptor signaling"],
    "Energy and society": ["energy policy", "energy transition", "household energy", "energy justice", "adoption"],
    "Energy science and technology": ["battery", "photovoltaic", "fuel cell", "supercapacitor", "energy storage", "electrocatalysis", "solar cell", "electrode"],
    "Engineering": ["engineering", "mechanical", "structural", "finite element", "prototype", "actuator", "load", "fabrication process"],
    "Environmental sciences": ["pollutant", "contaminant", "wastewater", "remediation", "environmental", "particulate", "emission"],
    "Environmental social sciences": ["environmental policy", "governance", "stakeholder", "conservation attitude", "perception"],
    "Evolution": ["evolution", "phylogeny", "selection pressure", "adaptation", "speciation", "ancestral", "fitness"],
    "Forestry": ["forest", "timber", "canopy", "deforestation", "tree ring", "silviculture", "biomass"],
    "Gastroenterology": ["gastrointestinal", "liver", "intestinal", "colon", "hepatic", "gut", "endoscopy"],
    "Genetics": ["gene", "allele", "mutation", "genotype", "heritability", "locus", "snp", "genomic"],
    "Geography": ["spatial", "gis", "land use", "geographic", "mapping", "remote sensing", "region"],
    "Health care": ["healthcare", "clinical care", "hospital", "treatment outcome", "quality of care", "intervention"],
    "Health occupations": ["nursing", "physician", "medical education", "clinical training", "workforce"],
    "Hydrology": ["groundwater", "runoff", "watershed", "streamflow", "aquifer", "hydrological", "discharge"],
    "Immunology": ["immune", "antibody", "t cell", "cytokine", "antigen", "immunization", "lymphocyte", "inflammation"],
    "Limnology": ["lake", "freshwater", "plankton", "eutrophication", "limnological", "reservoir"],
    "Materials science": ["material", "alloy", "composite", "microstructure", "mechanical properties", "hardness", "fracture", "polymer", "ceramic"],
    "Mathematics and computing": ["algorithm", "theorem", "proof", "computational complexity", "neural network", "optimization", "machine learning", "dataset"],
    "Medical research": ["clinical trial", "cohort", "randomized", "patient outcome", "medical", "therapeutic efficacy"],
    "Microbiology": ["bacteria", "microbial", "strain", "pathogen", "antibiotic", "colony", "microbiome", "fermentation"],
    "Molecular biology": ["transcription", "rna", "dna", "ribosome", "gene expression", "pcr", "clone", "vector"],
    "Molecular medicine": ["molecular mechanism", "disease model", "gene therapy", "signaling pathway", "translational"],
    "Nanoscience and technology": ["nanoparticle", "nanostructure", "quantum dot", "nanowire", "self-assembly", "nanoscale", "plasmonic"],
    "Natural hazards": ["earthquake", "flood", "landslide", "volcanic", "hazard", "seismic", "tsunami"],
    "Nephrology": ["kidney", "renal", "dialysis", "glomerular", "nephrology", "creatinine"],
    "Neurology": ["neurological", "brain", "neuron disorder", "epilepsy", "stroke", "alzheimer", "parkinson"],
    "Neuroscience": ["neuron", "synaptic", "cortex", "neural activity", "dopamine", "electrophysiology", "hippocampus", "axon"],
    "Ocean sciences": ["ocean", "seawater", "marine", "salinity", "phytoplankton", "oceanographic", "coastal"],
    "Oncology": ["oncology", "tumor suppressor", "carcinogenesis", "radiotherapy", "cancer cell line", "xenograft"],
    "Optics and photonics": ["photonic", "optical", "refractive index", "transmittance", "laser", "waveguide", "birefringence", "thin-film", "resonator", "spectrum", "quantum photonics"],
    "Pathogenesis": ["pathogen", "virulence", "infection", "host-pathogen", "colonization", "pathogenesis"],
    "Physics": ["quantum", "hamiltonian", "boson", "fermion", "symmetry breaking", "superconductivity", "condensed matter", "scattering", "magnetization"],
    "Physiology": ["physiological", "blood pressure", "respiration", "muscle", "homeostasis", "heart rate"],
    "Planetary science": ["mars", "lunar", "planetary", "crater", "regolith", "asteroid", "orbiter"],
    "Plant sciences": ["plant", "leaf", "photosynthesis", "root", "chlorophyll", "stomata", "arabidopsis"],
    "Psychology": ["cognitive", "behavior", "participants", "questionnaire", "psychological", "perception", "anxiety"],
    "Rheumatology": ["arthritis", "rheumatoid", "joint", "autoimmune", "inflammation joint", "lupus"],
    "Risk factors": ["risk factor", "odds ratio", "hazard ratio", "epidemiological", "exposure", "incidence"],
    "Scientific community": ["peer review", "citation", "reproducibility", "open science", "funding", "bibliometric"],
    "Signs and symptoms": ["symptom", "pain", "fever", "fatigue", "clinical sign", "presentation"],
    "Social sciences": ["social", "survey", "inequality", "policy", "demographic", "qualitative interview"],
    "Solid Earth sciences": ["geology", "mantle", "crust", "tectonic", "mineral", "seismic wave", "magma"],
    "Space physics": ["magnetosphere", "solar wind", "ionosphere", "plasma", "aurora", "cosmic ray"],
    "Stem cells": ["stem cell", "pluripotent", "differentiation", "regeneration", "organoid", "progenitor"],
    "Structural biology": ["crystal structure", "cryo-em", "x-ray crystallography", "protein structure", "residue", "conformation"],
    "Systems biology": ["network", "systems biology", "pathway analysis", "omics", "interaction network", "modeling"],
    "Urology": ["urinary", "prostate", "bladder", "urological", "kidney stone"],
    "Water resources": ["water resource", "irrigation", "water quality", "dam", "water management", "scarcity"],
    "Zoology": ["animal", "species", "mammal", "behavioral ecology", "morphological trait", "zoological"],
}

STOP_TOKENS = re.compile(r"\s+")


def load_overlay_terms(overlays_dir):
    terms = {}
    if not overlays_dir.is_dir():
        return terms
    for md in overlays_dir.glob("*.md"):
        field = md.stem
        collected = []
        in_section = False
        for line in md.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("## "):
                in_section = "top terms" in line.lower()
                continue
            if in_section:
                m = re.match(r"-\s*`?([A-Za-z][A-Za-z0-9 /-]+?)`?\s*(?:—|\(|$)", line.strip())
                if m:
                    collected.append(m.group(1).strip().lower())
        if collected:
            terms[field] = collected
    return terms


def score_text(text, overlay_terms):
    lowered = text.lower()
    scores = Counter()
    for field, terms in SEEDS.items():
        for term in terms:
            hits = len(re.findall(r"\b" + re.escape(term.lower()) + r"\b", lowered))
            scores[field] += hits * 2
    for field, terms in overlay_terms.items():
        for term in terms:
            hits = len(re.findall(r"\b" + re.escape(term) + r"\b", lowered))
            scores[field] += hits
    return scores


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top_n = 5
    if "--top" in sys.argv:
        i = sys.argv.index("--top")
        top_n = int(sys.argv[i + 1])
        args = [a for a in args if a != sys.argv[i + 1]]
    if not args:
        print("usage: route_field.py TEXTFILE [--top N]", file=sys.stderr)
        return 2
    with open(args[0], encoding="utf-8") as f:
        text = f.read()

    overlays_dir = Path(__file__).resolve().parent.parent / "references" / "overlays"
    scores = score_text(text, load_overlay_terms(overlays_dir))
    ranked = scores.most_common(top_n)
    if not ranked or ranked[0][1] == 0:
        print("0. (no field matched — provide the field explicitly)")
        return 0
    for rank, (field, score) in enumerate(ranked, 1):
        print(f"{rank}. {field} (score={score})")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    sys.exit(main())

