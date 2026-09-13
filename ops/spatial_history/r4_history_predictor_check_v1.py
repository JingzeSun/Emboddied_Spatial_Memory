"""D-099 synthetic L/R full-sequence checks; zero optimizer updates."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

from r4_model_assets_v1 import ASSETS, ROOT, record, write
from r4_native_models_v1 import no_dataset

RUN = ASSETS / 'history-predictor-check-v1'
FILES = ['src/spatial_world_model/' + name for name in
         ('r4_history_predictor.py', 'r4_torch_task.py', 'r4_model_inputs.py', 'r4_coverage.py',
          'r4_query_v2.py', 'pair_contract.py', 'two_gate_contract.py', '__init__.py')] + [
         'tests/spatial_world_model/r4_examples_v2.py',
         'ops/spatial_history/r4_history_predictor_check_v1.py',
         'ops/spatial_history/r4_model_assets_v1.py', 'ops/spatial_history/r4_native_models_v1.py',
         'docs/METHOD.md', 'docs/DATA.md', 'docs/DECISIONS.md']


def check():
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests/spatial_world_model')]
    import torch
    from r4_examples_v2 import public
    from spatial_world_model.r4_query_v2 import from_public_query
    from spatial_world_model.r4_history_predictor import HistoryPredictor, prepare_query
    torch.set_num_threads(4)
    torch.manual_seed(7927)
    torch.cuda.manual_seed_all(7927)
    query = from_public_query(public(range(121)))
    original = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()
    history, controls, goal, evidence = prepare_query(query)
    retrieved, _, _, selection = prepare_query(query, retrieval=True)
    assert evidence is None and selection['selected_local_indices'] == [0, 1, 2, 3, 4, 5, 6, 7, 119, 120]
    assert history['rgb'].shape == (1, 121, 3, 80, 80)
    assert retrieved['rgb'].shape == (1, 10, 3, 80, 80)
    assert torch.equal(retrieved['metadata'], history['metadata'][:, selection['selected_local_indices']])
    assert hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest() == original
    try:
        prepare_query(dict(query, private_geometry=[]))
    except ValueError:
        pass
    else:
        raise AssertionError('private key accepted')
    recent_query = from_public_query(public(), history_mode='recent')
    recent, _, _, recent_selection = prepare_query(recent_query, retrieval=True, history_mode='recent')
    assert recent_selection['selected_local_indices'] == [0, 1] and recent['rgb'].shape[1] == 2
    prefix_query = from_public_query(public(range(6)), history_mode='prefix', history_cut_index=5)
    prefix, _, _, prefix_selection = prepare_query(prefix_query, retrieval=True, history_mode='prefix', history_cut_index=5)
    assert prefix_selection['selected_local_indices'] == list(range(6))
    assert float(prefix['metadata'][0, -1, 17]) < 0
    model = HistoryPredictor().cuda().eval()
    with torch.no_grad():
        frames = model.encode_frames(history)
        assert frames.shape == (1, 121, 25, 256)
        state = model.observe(history)
        short_state = model.observe(retrieved)
        assert state['tokens'].shape == (1, 3025, 256)
        assert short_state['tokens'].shape == (1, 250, 256)
        saved = {key: value.clone() for key, value in state.items()}
        first = model.imagine(state, controls, goal)
        changed = controls.clone(); changed[:, 100, 0] = .5
        second = model.imagine(state, changed, goal)
        torch.testing.assert_close(first['future_features'][:, :100], second['future_features'][:, :100], rtol=0, atol=1e-6)
        assert not torch.allclose(first['future_features'][:, 100], second['future_features'][:, 100])
        for key in saved:
            assert torch.equal(saved[key], state[key])
        repeated = model.imagine(state, controls, goal)
        torch.testing.assert_close(repeated['future_features'], first['future_features'], rtol=0, atol=0)
        assert first['task']['object_position_m'].shape == (1, 200, 3)
        assert first['task']['contact_logit'].shape == (1, 200)
        assert first['task']['success_logit'].shape == (1,)
        assert all(torch.isfinite(v).all() for v in first['task'].values())
        invalid = {key: value.clone() for key, value in history.items()}
        invalid['depth_m'][~invalid['depth_valid']] = 12345
        torch.testing.assert_close(model.encode_frames(invalid), frames, rtol=0, atol=0)
        changed_history = {key: value.clone() for key, value in history.items()}
        changed_history['rgb'][:, 0] = 255
        assert not torch.allclose(model.observe(changed_history)['tokens'], state['tokens'])
    del frames, state, short_state, saved, first, second, repeated, invalid, changed_history
    labels = {'position_m': torch.zeros((1, 200, 3), device='cuda'),
              'contact': torch.zeros((1, 200), device='cuda', dtype=torch.bool),
              'success': torch.ones((1,), device='cuda', dtype=torch.bool)}
    results = {}
    for name, source in [('L', history), ('R', retrieved)]:
        model.zero_grad(set_to_none=True)
        model.train(); torch.manual_seed(7929); torch.cuda.manual_seed_all(7929)
        source = dict(source, depth_m=source['depth_m'].detach().clone().requires_grad_())
        began = time.monotonic()
        total, terms = model.loss(source, controls, goal, labels)
        total.backward(); torch.cuda.synchronize()
        elapsed = time.monotonic() - began
        assert torch.isfinite(total)
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
        assert source['depth_m'].grad[:, 0].abs().sum() > 0
        norms = {}
        for group in ('rgb', 'depth', 'metadata', 'previous_action', 'encoder', 'control', 'decoder', 'task'):
            values = [p.grad for key, p in model.named_parameters() if key.startswith(group + '.')]
            norms[group] = sum(float(g.square().sum()) for g in values) ** .5
            assert norms[group] > 0
        results[name] = {'full_backward_s': elapsed, 'gradient_l2': norms,
                         'loss_terms': {key: float(value) for key, value in terms.items()}}
        print(name, 'FULL HISTORY/200 BACKWARD COMPLETE', elapsed, flush=True)
    return {'checks': ['native_80_rgbd', 'L121_R10', 'coverage_tie_rule', 'original_timestamps',
             'public_query_unchanged', 'private_key_rejected', 'recent_two', 'prefix_six',
             'native_5x5_tokens', 'L3025_R250', 'future_control_causality', 'state_unchanged',
             'deterministic_replay', 'complete_200_task_shapes', 'finite_outputs',
             'invalid_depth_ignored', 'early_history_changes_state', 'L_full_backward',
             'R_full_backward', 'early_depth_gradient', 'eight_gradient_paths'],
            'parameter_count': sum(p.numel() for p in model.parameters()), 'backward': results,
            'max_cuda_allocated_bytes': torch.cuda.max_memory_allocated(),
            'new_training_steps': 0, 'optimizer_constructed': False, 'dataset_files_read': 0,
            'trained_model_ready': False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('step', choices=['run', 'export'])
    if parser.parse_args().step == 'export':
        artifacts = {p.name: {**record(p), 'text': p.read_text()} for p in RUN.glob('*.json')}
        write(ROOT / 'results/spatial_history_r4_history_predictor_v1.json',
              {'stage': 'R4-5-history-predictor-v1', 'artifacts': artifacts, 'exporter': record(Path(__file__))})
        print('L/R CHECK EXPORTED exit=0'); return
    assert sys.platform.startswith('linux')
    RUN.mkdir(exist_ok=False)
    binding = {name: record(ROOT / name) for name in FILES}
    write(RUN / 'started.json', {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'binding': binding})
    began = time.monotonic()
    def timeout(*_):
        raise TimeoutError('1800-second L/R engineering budget exceeded')
    signal.signal(signal.SIGALRM, timeout); signal.alarm(1800)
    sys.addaudithook(no_dataset)
    try:
        result = check()
        assert result['max_cuda_allocated_bytes'] <= 28 * 2**30
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= 12 * 2**30
        assert binding == {name: record(ROOT / name) for name in FILES}
        write(RUN / 'receipt.json', {'exit_code': 0, 'result': result, 'elapsed_s': time.monotonic() - began,
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              'started': record(RUN / 'started.json')})
        print('L/R CHECK COMPLETE checks=21 exit=0', flush=True)
    except BaseException as error:
        write(RUN / 'failure.json', {'exit_code': 1, 'error': repr(error), 'elapsed_s': time.monotonic() - began})
        raise


if __name__ == '__main__':
    main()
