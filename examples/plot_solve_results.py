from glob import glob
import os
from collections import OrderedDict
from typing import Dict, List, Tuple
import numpy as np
import matplotlib.pyplot as plt
import pltpublish as pub
import csv


from plot_helper import (
    plot_y_wrt_x,
    make_plot_wrapper,
    plot_dist,
    plot_rank_by,
)


def load_data(
    dataset_name: str, output_folder: str, verbose: bool = False
) -> Tuple[Dict[str, Dict[int, List]], float]:
    # Dict[name, Dict[seed, data]]
    methods = {}
    timeout = 1e99
    all_search = set()
    all_solver = set()

    for file in glob(os.path.join(output_folder, "*.csv")):
        filename = os.path.relpath(file, output_folder)
        if verbose:
            print("found csv file:", file)
        # filename should be {dataset_name}_seed_{seed}_{name}.csv
        if not filename.startswith(dataset_name):
            if verbose:
                print(f"\tskipped: does not start with {dataset_name}")
            continue
        name = filename[len(dataset_name) : -4]
        if "_seed_" not in name:
            if verbose:
                print(f"\tskipped: does not contain _seed_")
            continue
        search = name[1 : name.index("_seed_")].replace("_", " ")
        all_search.add(search)
        name = name[name.index("_seed_") + len("_seed_") :]
        seed = int(name[: name.index("_")])
        solver = name[name.index("_") + 1 :].replace("_", " ")
        all_solver.add(solver)
        name = search + " " + solver
        if name not in methods:
            methods[name] = {}
        if seed in methods[name]:
            print(f"Warning: duplicate seed {seed} for method {name}!")
            continue
        # Load data from the file
        trace = []
        with open(os.path.join(output_folder, filename), "r") as fd:
            reader = csv.reader(fd)
            trace = [tuple(row) for row in reader]
            # Pop columns names
            columns = {name: ind for ind, name in enumerate(trace.pop(0))}
            indices = [
                columns["solved"],
                columns["time"],
                columns["programs"],
                columns.get("merged", -1),
                columns.get("restarts", -1),
            ]
            data = [tuple(row[k] if k >= 0 else 0 for k in indices) for row in trace]
            # Type conversion (success, time, num_of_programs)
            trace = [
                (
                    int(row[0] == "True"),
                    float(row[1]),
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                )
                for row in data
            ]
            for x in trace:
                if x[0] == 0:
                    timeout = min(x[1], timeout)
        if len(trace) == 0:
            if verbose:
                print(f"\tskipped: no data")
            continue
        # Save data for method
        methods[name][seed] = trace
        if verbose:
            print(
                f"{name} (seed={seed}) solved",
                sum(x[0] for x in trace),
                "/",
                len(trace),
            )
    if len(all_search) == 1 and len(all_solver) > 1:
        search = list(all_search)[0]
        methods = {
            k.replace(search, "").strip(" ").capitalize(): v for k, v in methods.items()
        }
    elif len(all_solver) == 1 and len(all_search) > 1:
        solver = list(all_solver)[0]
        methods = {
            k.replace(solver, "").strip(" ").capitalize(): v for k, v in methods.items()
        }
    return methods, timeout


def make_filter_wrapper(func, *args) -> None:
    def f(task_index: int, methods: Dict[str, Dict[int, List]], timeout: float) -> bool:
        return func(task_index, methods, timeout, *args)

    return f


def timeout_filter(
    task_index: int,
    methods: Dict[str, Dict[int, List]],
    timeout: float,
    nbr_timeouts: int,
) -> bool:
    timeouts = 0
    for method, seeds_dico in methods.items():
        if nbr_timeouts == -1:
            nbr_timeouts = len(methods) * len(seeds_dico)
        for seed, data in seeds_dico.items():
            timeouts += 1 - data[task_index][0]
            if timeouts > nbr_timeouts:
                return False

    return True


def time_filter(
    task_index: int,
    methods: Dict[str, Dict[int, List]],
    timeout: float,
    ratio: float,
    aggregator,
) -> bool:
    all_times = []
    for method, seeds_dico in methods.items():
        for seed, data in seeds_dico.items():
            all_times.append(data[task_index][1])
    return aggregator(all_times) >= ratio * timeout


def reverse_filter(func):
    def f(
        task_index: int, methods: Dict[str, Dict[int, List]], timeout: float, *args
    ) -> bool:
        return not func(task_index, methods, timeout, *args)

    return f


__FILTERS__ = {
    "timeouts.none": make_filter_wrapper(timeout_filter, 1),
    "solve>=1": make_filter_wrapper(timeout_filter, -1),
}

for ratio in [0.25, 0.5, 0.75]:
    for name, aggr in [
        ("fastest", np.min),
        ("mean", np.mean),
        ("median", np.median),
        ("slowest", np.max),
    ]:
        __FILTERS__[f"time.{name}>={ratio:.0%}"] = make_filter_wrapper(
            time_filter, ratio, aggr
        )

for key in list(__FILTERS__.keys()):
    __FILTERS__[f"not.{key}"] = reverse_filter(__FILTERS__[key])


def filter(
    methods: Dict[str, Dict[int, List]], filter_name: str, timeout: float
) -> Dict[str, Dict[int, List]]:
    fun = __FILTERS__[filter_name]
    task_len = len(list(list(methods.values())[0].values())[0])
    should_keep = [fun(i, methods, timeout) for i in range(task_len)]
    return {
        m: {
            s: [x for i, x in enumerate(data) if should_keep[i]]
            for s, data in val.items()
        }
        for m, val in methods.items()
    }


__DATA__ = {
    "tasks": (0, "Tasks completed", 10, True, True),
    "time": (1, "Time (in s)", 5, False, False),
    "programs": (2, "Programs Enumerated", 0, False, False),
    "merges": (3, "Programs Merged", 0, False, False),
    "restarts": (4, "Retsarts", 0, False, False),
}


# Generate all possible combinations
__PLOTS__ = {}
for ydata in list(__DATA__.keys()):
    for xdata in list(__DATA__.keys()):
        if xdata == ydata:
            continue
        __PLOTS__[f"{ydata}_wrt_{xdata}"] = make_plot_wrapper(
            plot_y_wrt_x, __DATA__[xdata], __DATA__[ydata]
        )
    if ydata != "tasks":
        __PLOTS__[f"rank_by_{ydata}"] = make_plot_wrapper(plot_rank_by, __DATA__[ydata])
        __PLOTS__[f"dist_{ydata}_by_task"] = make_plot_wrapper(
            plot_dist, __DATA__[ydata], "tasks"
        )


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Plot results")
    parser.add_argument(
        "-d",
        "--dataset",
        type=str,
        default="dataset.pickle",
        help="dataset (default: dataset.pickle)",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="./",
        help="folder in which to look for CSV files (default: './')",
    )
    parser.add_argument(
        "--sorted", action="store_true", help="sort data by task solving time"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="verbose mode",
    )
    parser.add_argument(
        "--filter",
        type=str,
        nargs="*",
        choices=list(__FILTERS__.keys()),
        help="filter tasks (keep data based on the filter)",
    )
    parser.add_argument("plots", nargs="+", choices=list(__PLOTS__.keys()))
    parameters = parser.parse_args()
    dataset_file: str = parameters.dataset
    output_folder: str = parameters.folder
    verbose: bool = parameters.verbose
    no_sort: bool = not parameters.sorted
    plots: List[str] = parameters.plots
    filters: List[str] = parameters.filter or []

    # Initial Setup
    start_index = (
        0
        if not os.path.sep in dataset_file
        else (len(dataset_file) - dataset_file[::-1].index(os.path.sep))
    )
    dataset_name = dataset_file[start_index : dataset_file.index(".", start_index)]
    # Load data
    pub.setup()
    methods, timeout = load_data(dataset_name, output_folder, verbose)
    # Check we have at least one file
    if len(methods) == 0:
        print("Error: no performance file was found!", file=sys.stderr)
        sys.exit(1)
    for filter_name in filters:
        methods = filter(methods, filter_name, timeout)
        # Check we did not remove everything
        task_len = len(list(list(methods.values())[0].values())[0])
        if task_len == 0:

            print("Error: filters left no tasks!", file=sys.stderr)
            sys.exit(1)
    # Order by name so that it is always the same color for the same methods if diff. DSL
    ordered_methods = OrderedDict()
    for met in sorted(methods.keys()):
        ordered_methods[met] = methods[met]
    # Plotting
    for count, to_plot in enumerate(plots):
        ax = plt.subplot(1, len(plots), count + 1)
        __PLOTS__[to_plot](ax, ordered_methods)
    plt.show()
