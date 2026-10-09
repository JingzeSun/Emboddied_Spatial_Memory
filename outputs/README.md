# Outputs

Large run outputs are not tracked. The stage drivers write to `/root/autodl-tmp/vsmt_outputs/` and
`/root/autodl-tmp/vsmt_private/` on the servers (run roots, logs, per-episode audits, weights); each stage exports its
reports, manifests and digests as `results/vsmt_lean_*_<tag>.json`, which are committed. [docs/REPRODUCE.md](../docs/REPRODUCE.md)
lists the outputs of every stage. This local directory is ignored except for this file.
