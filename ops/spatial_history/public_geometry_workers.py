"""Bounded process scheduling only; no geometry, input loading, or evaluation.

``dispatch`` owns handle lifetime. Callbacks own process creation, resource
checks, termination, and receipts. Run it in the parent main thread; any helper
threads must also block the stage's asynchronous termination signals.
"""
from contextlib import contextmanager
import math
import signal
import time


@contextmanager
def _signals_blocked():
    """Register a newly launched child before a stage signal can abort us."""
    if not hasattr(signal, "pthread_sigmask"):
        yield
        return
    watched = {getattr(signal, name) for name in ("SIGTERM", "SIGINT", "SIGALRM", "SIGUSR1")
               if hasattr(signal, name)}
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, watched)
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def dispatch(tasks, workers, launch, completed, checkpoint, abort, *, interval_s=0.05):
    """Run at most ``workers`` children and return receipts in task order.

    Each task is a dict with a unique, hashable ``id``. ``launch(task)`` returns
    a process-like object with ``poll`` and ``wait``. ``checkpoint()`` checks
    whole-stage resource limits. ``completed(task, handle, error)`` persists a
    receipt, and must reject nonzero exits after saving them. It is called only
    after the child has been waited for, at most once per launched child.
    ``abort(handle)`` must terminate its process group and wait for the child.

    A callback or polling failure stops new launches and attempts cleanup for
    every remaining handle. Cleanup failures are notes on the original error;
    they cannot stop cleanup of another child. No failed task is retried.
    """
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("workers must be an integer from 1 through 16")
    if (type(interval_s) not in (int, float) or not math.isfinite(interval_s)
            or interval_s < 0):
        raise ValueError("interval_s must be a finite nonnegative number")
    tasks = list(tasks)
    identifiers = set()
    for task in tasks:
        if not isinstance(task, dict) or "id" not in task:
            raise ValueError("each task must be a dict with id")
        try:
            if task["id"] in identifiers:
                raise ValueError("task ids must be unique")
            identifiers.add(task["id"])
        except TypeError as error:
            raise ValueError("task ids must be hashable") from error
    active = []
    results = [None] * len(tasks)
    next_index = 0
    try:
        while next_index < len(tasks) or active:
            checkpoint()
            while next_index < len(tasks) and len(active) < workers:
                checkpoint()
                task = tasks[next_index]
                with _signals_blocked():
                    handle = launch(task)
                    active.append({"task": task, "handle": handle, "index": next_index,
                                   "waited": False, "callback_started": False})
                next_index += 1
            checkpoint()
            for entry in list(active):
                handle = entry["handle"]
                if handle.poll() is None:
                    continue
                handle.wait()
                entry["waited"] = True
                # Mark before invoking: a partially written receipt must not
                # cause another call when the callback itself raises.
                entry["callback_started"] = True
                results[entry["index"]] = completed(entry["task"], handle, None)
                active.remove(entry)
                checkpoint()
            if active:
                time.sleep(interval_s)
        return results
    except BaseException as error:
        cleanup_errors = []
        cancellation = f"cancelled after {type(error).__name__}: {error}"
        try:
            # Finish all cleanup attempts before servicing another signal.
            with _signals_blocked():
                for entry in active:
                    handle = entry["handle"]
                    task_id = repr(entry["task"]["id"])
                    if not entry["waited"]:
                        try:
                            abort(handle)
                            entry["waited"] = True
                        except BaseException as cleanup_error:
                            cleanup_errors.append(f"{task_id} abort: {type(cleanup_error).__name__}: "
                                                  f"{cleanup_error}")
                            # An abort can fail after the child has exited. In
                            # that case reaping is safe; never block on a child
                            # that the failed abort left running.
                            try:
                                if handle.poll() is not None:
                                    handle.wait()
                                    entry["waited"] = True
                            except BaseException as reap_error:
                                cleanup_errors.append(f"{task_id} reap: {type(reap_error).__name__}: "
                                                      f"{reap_error}")
                    if entry["waited"] and not entry["callback_started"]:
                        entry["callback_started"] = True
                        try:
                            completed(entry["task"], handle, cancellation)
                        except BaseException as receipt_error:
                            cleanup_errors.append(f"{task_id} receipt: {type(receipt_error).__name__}: "
                                                  f"{receipt_error}")
        except BaseException as signal_error:
            cleanup_errors.append(f"cleanup signal mask: {type(signal_error).__name__}: {signal_error}")
        if cleanup_errors:
            error.add_note("dispatch cleanup errors:\n" + "\n".join(cleanup_errors))
        raise
