import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "ops/vsmt")
from vsmt import lean_model as model
import ruling89_probes as probes
D = "/root/autodl-tmp/vsmt_private/ruling91-75c0f4d/probes/imitation"
SRC = "/root/autodl-tmp/vsmt_private/ruling89-sides-003b906:dagger_round_0:ELU-P"
groups, split, _ = probes.load_groups([SRC])
out = {}
for target in ("elup", "rac", "handcost"):
    payload = json.load(open(f"{D}/imitation_{target}_weights.json"))
    heads = model.load_heads(payload).eval()
    built = {g: [probes.imitation_record(row, target) for _, _, row in rows] for g, rows in groups.items()}
    offset = heads.existence_logit_offset
    res = {}
    for label, value in (("corrected", offset), ("uncorrected", 0.0)):
        heads.existence_logit_offset = value
        res[label] = {g: probes.agreement(heads, b, target) for g, b in built.items()}
    out[target] = {"offset": offset, "epoch": payload["training"]["best_epoch"],
                   **{f"{k}_{g}": {"balanced": round(v[g]["balanced_agreement"], 4),
                                   "per_class": {c: round(x["agreement"], 4) for c, x in v[g]["per_class"].items()}}
                      for k, v in res.items() for g in ("train", "selection")}}
    print(target, json.dumps(out[target]), flush=True)
json.dump({"stage": "ruling91 P3 offset diagnostic (read-only, report only)", "results": out},
          open("/root/autodl-tmp/vsmt_outputs/exports/vsmt_lean_ruling91_p3_offset_diagnostic_75c0f4d.json", "w"), indent=1)
