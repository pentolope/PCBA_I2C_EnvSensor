from __future__ import annotations

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(REPO_ROOT, "evidence", "index.json")
DATASHEET_DIR = os.path.join(REPO_ROOT, "evidence", "datasheets")

SOURCES = {
    "sht40_sensirion": {
        "file": "datasheets/sht40_sensirion.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2304140030_Sensirion-SHT40-AD1B-R3_C2848306.pdf",
        "retrieved": "2026-09-01",
        "document_id": "Sensirion SHT4x datasheet Version 1, October 2020",
        "applies_to": ["SHT40-AD1B-R3"],
    },
    "lps22hb_st": {
        "file": "datasheets/lps22hb_st.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "1810121116_STMicroelectronics-LPS22HBTR_C94049.pdf",
        "retrieved": "2026-09-01",
        "document_id": "STMicroelectronics LPS22HB DocID027083 Rev 6",
        "applies_to": ["LPS22HBTR"],
    },
    "opt3001_ti": {
        "file": "datasheets/opt3001_ti.pdf",
        "url": "https://www.ti.com/lit/ds/symlink/opt3001.pdf",
        "retrieved": "2026-09-01",
        "document_id": "SBOS681C",
        "applies_to": ["OPT3001DNPR"],
    },
    "tpd2e2u06_ti": {
        "file": "datasheets/tpd2e2u06_ti.pdf",
        "url": "https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf",
        "retrieved": "2026-09-01",
        "document_id": "SLLSEG9C",
        "applies_to": ["TPD2E2U06DRLR"],
    },
    "tpd1e10b06_ti": {
        "file": "datasheets/tpd1e10b06_ti.pdf",
        "url": "https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf",
        "retrieved": "2026-09-01",
        "document_id": "SLLSEB1",
        "applies_to": ["TPD1E10B06DPYR"],
    },
    "ph_series_jst": {
        "file": "datasheets/ph_series_jst.pdf",
        "url": "https://www.jst-mfg.com/product/pdf/eng/ePH.pdf",
        "retrieved": "2026-09-01",
        "document_id": "JST PH connector series catalogue",
        "applies_to": ["S4B-PH-K-S(LF)(SN)"],
    },
    "s4b_ph_k_s_jst": {
        "file": "datasheets/s4b_ph_k_s_jst.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2304140030_JST-S4B-PH-K-S-LF-SN_C157926.pdf",
        "retrieved": "2026-09-01",
        "document_id": "JST PH catalogue page for S4B-PH-K-S",
        "applies_to": ["S4B-PH-K-S(LF)(SN)"],
    },
    "i2c_um10204_nxp": {
        "file": "datasheets/i2c_um10204_nxp.pdf",
        "url": "https://www.pololu.com/file/0J435/UM10204.pdf",
        "retrieved": "2026-09-01",
        "document_id": "NXP UM10204 Rev. 7.0, 1 October 2021",
        "applies_to": ["SHT40-AD1B-R3", "LPS22HBTR", "OPT3001DNPR"],
    },
    "uniroyal_0402wgf": {
        "file": "datasheets/uniroyal_0402wgf.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2206010045_UNI-ROYAL-Uniroyal-Elec-0402WGF2201TCE_"
               "C25879.pdf",
        "retrieved": "2026-09-01",
        "document_id": "Uniroyal thick film chip resistor specification",
        "applies_to": ["0402WGF2701TCE", "0402WGF470KTCE"],
    },
    "samsung_mlcc_cl_series": {
        "file": "datasheets/samsung_mlcc_cl_series.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2304140030_Samsung-Electro-Mechanics-CL05B104KO5NNNC_"
               "C1525.pdf",
        "retrieved": "2026-09-01",
        "document_id": "Samsung Electro-Mechanics MLCC CL series "
                       "specification",
        "applies_to": ["CL05B104KO5NNNC", "CL10A105KB8NNNC"],
    },
}


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_index():
    entries = {}
    for name in sorted(SOURCES):
        source = SOURCES[name]
        path = os.path.join(REPO_ROOT, "evidence", source["file"])
        entry = dict(source)
        entry["sha256"] = digest(path)
        entry["bytes"] = os.path.getsize(path)
        entries[name] = entry
    return {"schema_version": 1, "documents": entries}


def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_index():
    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(compute_index(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return INDEX_PATH


def verify():
    recorded = load_index()["documents"]
    present = {name for name in os.listdir(DATASHEET_DIR)
               if name.endswith((".pdf", ".json"))}
    referenced = {os.path.basename(entry["file"])
                  for entry in recorded.values()}
    problems = []
    for name in sorted(referenced - present):
        problems.append(("missing_file", name))
    for name in sorted(present - referenced):
        problems.append(("unreferenced_file", name))
    for name in sorted(recorded):
        entry = recorded[name]
        path = os.path.join(REPO_ROOT, "evidence", entry["file"])
        if not os.path.isfile(path):
            continue
        if digest(path) != entry["sha256"]:
            problems.append(("digest_mismatch", name))
    return problems


if __name__ == "__main__":
    sys.stdout.write(write_index() + "\n")
