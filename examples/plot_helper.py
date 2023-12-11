import numpy as np

import matplotlib.pyplot as plt

from typing import List, Optional, Dict, Tuple


def plot_with_incertitude(
    ax: plt.Axes,
    x: List[np.ndarray],
    y: List[np.ndarray],
    label: str,
    std_factor: float = 1.96,
    miny: Optional[float] = None,
    maxy: Optional[float] = None,
) -> None:
    max_len = max(len(xi) for xi in x)
    x = [xi for xi in x if len(xi) == max_len]
    y = [yi for yi in y if len(yi) == max_len]

    x_min = np.min(np.array(x))
    x_max = np.max(np.array(x))
    if x_max == x_min:
        return
    target_x = np.arange(x_min, x_max + 1, step=(x_max - x_min) / 50)
    # Interpolate data
    data = []
    for xi, yi in zip(x, y):
        nyi = np.interp(target_x, xi, yi)
        data.append(nyi)
    # Compute distribution
    Y = np.array(data)
    mean = np.mean(Y, axis=0)
    std = std_factor * np.std(Y, axis=0)

    p = ax.plot(target_x, mean, label=label)
    color = p[0].get_color()
    upper = mean + std
    if maxy is not None:
        upper = np.minimum(upper, maxy)
    lower = mean - std
    if miny is not None:
        lower = np.maximum(lower, miny)
    ax.fill_between(target_x, lower, upper, color=color, alpha=0.5)


def make_plot_wrapper(func, *args) -> None:
    def f(ax: plt.Axes, methods: Dict[str, Dict[int, List]]) -> None:
        return func(ax, methods, *args)

    return f


def plot_y_wrt_x(
    ax: plt.Axes,
    methods: Dict[str, Dict[int, List]],
    x_data: Tuple,
    y_data: Tuple,
    should_sort: bool = False,
) -> None:
    # Plot data with incertitude
    a_index, a_name, a_margin, show_len_a, _ = y_data
    b_index, b_name, b_margin, show_len_b, _ = x_data
    max_a = 0
    max_b = 0
    data_length = 0
    for method, seeds_dico in methods.items():
        seeds = list(seeds_dico.keys())
        data = [
            [(elems[b_index], elems[a_index]) for elems in seeds_dico[seed]]
            for seed in seeds
        ]
        data_length = max(data_length, len(data[0]))
        if should_sort:
            data = [sorted(seed_data) for seed_data in data]
        xdata = [np.cumsum([x[0] for x in seed_data]) for seed_data in data]
        ydata = [np.cumsum([x[1] for x in seed_data]) for seed_data in data]
        max_a = max(max(np.max(yi) for yi in ydata), max_a)
        max_b = max(max(np.max(xi) for xi in xdata), max_b)
        plot_with_incertitude(
            ax,
            xdata,
            ydata,
            method.capitalize(),
            maxy=data_length if show_len_a else None,
        )
    ax.set_xlabel(b_name)
    ax.set_ylabel(a_name)
    ax.grid()
    if show_len_a:
        ax.hlines(
            [data_length],
            xmin=0,
            xmax=max_b + b_margin,
            label=f"All {a_name}",
            color="k",
            linestyles="dashed",
        )
        max_a = data_length
    ax.set_xlim(0, max_b + b_margin)
    ax.set_ylim(0, max_a + a_margin)
    ax.legend()


def get_rank_matrix(
    methods: Dict[str, Dict[int, List]], yindex: int, maximize: bool
) -> Tuple[List[str], np.ndarray]:
    seeds = list(methods.values())[0].keys()
    task_len = len(list(list(methods.values())[0].values())[0])
    rank_matrix = np.ndarray((len(methods), task_len, len(methods)), dtype=float)
    method_names = list(methods.keys())
    data = np.ndarray((len(methods), len(seeds)), dtype=float)
    np.random.seed(1)
    for task_no in range(task_len):
        for i, method in enumerate(method_names):
            for j, seed in enumerate(seeds):
                data[i, j] = methods[method][seed][task_no][yindex]
        # data_for_seed = []
        # for method in method_names:
        #     data = methods[method][seed]
        #     data_for_seed.append([d[yindex] for d in data])
        # data_for_seed = np.array(data_for_seed)
        if maximize:
            data = -data
        rand_x = np.random.random(size=data.shape)
        # This is done to randomly break ties.
        # Last key is the primary key,
        indices = np.lexsort((rand_x, data), axis=0)
        for i, method in enumerate(method_names):
            rank_matrix[i, task_no] = [
                np.sum(indices[i] == rank) / len(seeds) for rank in range(len(methods))
            ]
    return rank_matrix


def __ready_for_stacked_dist_plot__(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(
        axis="both",
        which="both",
        bottom=False,
        top=False,
        left=True,
        right=False,
        labeltop=False,
        labelbottom=True,
        labelleft=True,
        labelright=False,
    )

    ax.legend(fancybox=True, fontsize="large")


def plot_rank_by(
    ax: plt.Axes, methods: Dict[str, Dict[int, List]], y_data: Tuple
) -> None:
    width = 1.0
    a_index, a_name, a_margin, show_len_a, should_max = y_data
    rank_matrix = get_rank_matrix(methods, a_index, should_max)
    labels = list(range(1, len(methods) + 1))
    mean_ranks = np.mean(rank_matrix, axis=-2)
    bottom = np.zeros_like(mean_ranks[0])
    for i, key in enumerate(methods.keys()):
        label = key
        bars = ax.bar(
            labels,
            mean_ranks[i],
            width,
            label=label,
            bottom=bottom,
            alpha=0.9,
            linewidth=1,
            edgecolor="white",
        )
        ax.bar_label(bars, labels=[f"{x:.1%}" for x in mean_ranks[i]])
        bottom += mean_ranks[i]

    ax.set_ylabel("Fraction (in %)", size="large")
    yticks = np.array(range(0, 101, 20))
    ax.set_yticklabels(yticks)
    ax.set_yticks(yticks * 0.01)
    ax.set_xlabel("Ranking", size="large")
    ax.set_xticks(labels)
    ax.set_xticklabels(labels)
    __ready_for_stacked_dist_plot__(ax)
    word = "Most" if should_max else "Least"
    ax.set_title(f"{word} {a_name}")


def plot_dist(
    ax: plt.Axes, methods: Dict[str, Dict[int, List]], y_data: Tuple, x_axis_name: str
) -> None:
    width = 1.0
    data_length = 0
    a_index, a_name, a_margin, show_len_a, should_max = y_data
    max_a = max(
        max(max([y[a_index] for y in x]) for x in seed_dico.values())
        for seed_dico in methods.values()
    )
    bottom = None
    nbins = 5
    bins = [max_a]
    while len(bins) <= nbins:
        bins.insert(0, np.sqrt(bins[0] + 1))
    for i in range(nbins):
        if bins[i + 1] < 2 * bins[i]:
            bins[i + 1] = 2 * bins[i]
    x_bar = list(range(1, nbins + 1))
    for method, seeds_dico in methods.items():
        hists = []
        for seed, raw_data in seeds_dico.items():
            data = [x[a_index] for x in raw_data]
            data_length = max(data_length, len(data))
            hist, edges = np.histogram(
                data, bins=bins, range=(1e-3, max_a), density=False
            )
            hists.append(hist)
        true_hist = np.mean(hists, axis=0) / data_length
        if bottom is None:
            bottom = np.zeros_like(true_hist)
        label = method
        bars = ax.bar(
            x_bar,
            true_hist,
            width,
            label=label,
            bottom=bottom,
            alpha=0.9,
            linewidth=1,
            edgecolor="white",
        )
        ax.bar_label(bars, labels=[f"{x:.1%}" for x in true_hist])
        bottom += true_hist
    __ready_for_stacked_dist_plot__(ax)
    ax.set_yticklabels([])
    ax.set_xlabel(a_name, size="large")
    ax.set_xticklabels(map(lambda x: f"<{x:.0f}", edges))
    ax.set_title(f"Distribution of {a_name} per {x_axis_name}")