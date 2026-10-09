"""Minimal example: the memory on one released ProcTHOR episode, fed frame by frame as an RGB-D stream.

Each frame is read as a robot would provide it -- RGB, metric depth, intrinsics, a causal camera pose and the instance
masks (here the SAM 2.1 masks stored with the episode) -- and passed to ``VSMTMemory.step``.  The example prints the
atoms of the first frames, a summary every 50 frames, and the final entity table.  With ``--check`` it replays the
episode's sealed cache through the same memory and reports whether both paths committed the same atoms.

Data: one validation episode from Hugging Face layer T1 (about 160 MB) and the weights from T0 (about 100 MB):

    python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-eval --repo-type dataset \\
        --revision 1bb81d27554d3795439172c418dc1416bff0c56e --dest <data root> \\
        --select validation/raw/procthor10k-0.1.2-train-02318.tar validation/sam2_cache/procthor10k-0.1.2-train-02318.tar
    python -m vsmt_memory.examples.hf_episode --data-root <data root>
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

from vsmt_memory import VSMTMemory
from vsmt_memory.episodes import HfEpisode

RAW = "vsmt_outputs/s3-02-3f6ef1d/validation"
CACHE = "vsmt_caches/s3-02-sam2-3f6ef1d/validation"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-root", required=True, type=Path, help="the --dest given to hf_fetch.py")
    parser.add_argument("--episode", default="procthor10k-0.1.2-train-02318")
    parser.add_argument("--frames", type=int, default=None, help="stop after this many frames")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--check", action="store_true", help="also replay the sealed cache and compare the atoms")
    args = parser.parse_args()

    episode = HfEpisode(args.data_root / RAW / args.episode, args.data_root / CACHE / args.episode)
    count = min(episode.frame_count, args.frames or episode.frame_count)
    memory = VSMTMemory.from_pretrained(front_end="sam2", seed=args.seed, episode_id=args.episode)
    totals: Counter[str] = Counter()
    programs = []
    started = time.time()
    for index in range(count):
        frame = episode.public_frame(index)
        result = memory.step(frame["rgb"], frame["depth_m"], frame["intrinsics"], frame["pose"], frame["masks"])
        programs.append([(op.atom, op.fragment_id) for op in result.program])
        totals.update(op.atom for op in result.program)
        if index < 3:
            for op in result.program:
                print(f"frame {result.tick}: {op.atom:10s} entity {op.entity_id[:20]}  mask {op.mask_index}")
        if result.tick % 50 == 0 or index == count - 1:
            states = Counter(entity.state for entity in result.entities)
            print(f"frame {result.tick:4d}: atoms so far {dict(totals)}; entities {dict(states)}; "
                  f"{(time.time() - started) / result.tick:.2f} s/frame")

    print("\nentity table (first 10 of", len(memory.entities()), "):")
    for entity in memory.entities()[:10]:
        print(f"  {entity.entity_id[:20]}  {entity.state:9s}  versions {entity.version_count:3d}  "
              f"seen {entity.observation_count:3d}x, last at frame {entity.last_seen_tick}  "
              f"centre {tuple(round(c, 2) for c in entity.centroid_m)}")

    if args.check:
        replay = VSMTMemory(memory.weights, episode_id=args.episode)
        same = sum(programs[i] == [(op.atom, op.fragment_id) for op in replay.step_cache_frame(episode.cache_frame(i)).program]
                   for i in range(count))
        print(f"\nsealed-cache replay: {same} of {count} frames committed the same atoms on the same fragments")


if __name__ == "__main__":
    main()
