"""
Convenience functions for plotting results.
"""

from util.calc import get_portrait_square

import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from itertools import cycle
from random import shuffle
from typing import Callable, Literal
import math

USABLE_MARKERS = ['.', 'o', 'v', '^', '<', '>', '1', '2', '3', '4', '8', 's', 'p', 'P', '*', 'h', '+', 'x', 'X', 'D']

DATA_WIDTH_DEFAULT = [1, 2, 4, 8]
SPARSITY_DEFAULT = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
COLOR_LIST_DEFAULT = [
    ['#fb6a4a', '#fcae91', '#d9181d'],
    ['#41b6c4', '#a1cac4', '#225ea8'],
    ['#74c476', '#bae4b3', '#238b45'],
    ['#fd8d3c', '#fdbe85', '#d94701'],
    ['#6baed6', '#bdd7e7', '#2171b5'],
    ['#78c679', '#c2e699', '#238443']
]

def plot_trend(mat_list: list[np.ndarray], labels: list[str], color_list=COLOR_LIST_DEFAULT, xlabel='', ylabel='', title='', save_name=''):
    assert len(mat_list) == len(labels)

    for idx in range(len(mat_list)):
        mat = mat_list[idx]
        label_name = labels[idx]
        data = mat / np.amax(mat, axis=0)
        # print(data)
        x_values = SPARSITY_DEFAULT

        # Calculate statistics
        means = np.mean(data, axis=1)
        lower_bound = np.min(data, axis=1)
        percentile_25 = np.percentile(data, 25, axis=1)
        # percentile_50 = np.percentile(data, 50, axis=1)
        percentile_75 = np.percentile(data, 75, axis=1)
        upper_bound = np.max(data, axis=1)

        # Plotting
        bar_width = 0.05

        transparency = 0.9

        for i, x in enumerate(x_values):
            plt.errorbar(x, means[i], yerr=[[means[i] - lower_bound[i]], [upper_bound[i] - means[i]]], color=color_list[idx][0], capsize=5, label='', alpha=transparency)
            plt.errorbar(x, means[i], yerr=[[means[i] - percentile_25[i]], [percentile_75[i] - means[i]]], elinewidth=10, color=color_list[idx][1], capsize=0, label='', alpha=transparency)

        # plot mean at top of the graph
        plt.plot(x_values, means, color=color_list[idx][2], label=label_name, linewidth=1, alpha=transparency)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    if (save_name is not None) and (save_name != ''):
        plt.savefig(save_name, dpi=600)

    # plt.show()
    plt.clf()
    plt.close()


def plot_result_3d(axis1, axis2, datapoints, description1='', description2='', description3='', title='', save_name='', elevation=25, azimuth=-145, alpha=1.0):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    _x = np.arange(len(axis1))
    _y = np.arange(len(axis2))
    _xx, _yy = np.meshgrid(_x, _y)
    x, y = _xx.ravel(), _yy.ravel()

    # Heights of bars are given by frequency
    datapoints = np.array(datapoints).T  # for unknown reason, datapoints is transposed, then it is correctly converted to 3d bar plot
    top = datapoints.ravel()
    bottom = np.zeros_like(top)

    # Change the width and depth here to make bars thinner
    width = depth = 0.5

    # Normalize to [0,1]
    norm = plt.Normalize(top.min(), top.max())

    # Create colormap
    colors = cm.Reds(norm(top))

    ax.bar3d(x, y, bottom, width, depth, top, color=colors, shade=True, edgecolor='black', alpha=alpha)
    ax.set_xticks(_x)
    ax.set_yticks(_y)
    ax.set_xticklabels(axis1)
    ax.set_yticklabels(axis2)
    ax.set_xlabel(description1)
    ax.set_ylabel(description2)
    ax.set_zlabel(description3)
    # Set the view angle
    ax.view_init(elev=elevation, azim=azimuth)
    ax.set_title(title)
    # save the figure in png with white background and high resolution
    if save_name != '':
        plt.savefig(save_name, bbox_inches='tight', pad_inches=1, transparent=False, dpi=600)

    plt.clf()
    plt.close(fig)

def plot_xy(
        df: pd.DataFrame, 
        group_identifiers: list[str], 
        x_axis_col: str | list[str], 
        y_axis_col: str | list[str], 
        subplots_identifiers: list[str] = None,
        subplots_df_modifier: Callable[[pd.DataFrame], pd.DataFrame] = None,
        y_axis_col_secondary: str = None,
        x_axis_label: str | list[str] = None,
        y_axis_label: str | list[str] = None, 
        y_axis_label_secondary: str = None,
        subplot_size_inches: tuple[int, int] = (6, 4), 
        save_path: str = None,
        short_labels: dict[str, str] = None,
        plot_type_2d: Literal['line', 'bar'] = 'bar',
        group_order: list[any] = None,
        normalized_y_axes: list[str] = [],
    ) -> None:
    """
    Plots a multi-line XY graph.

    Required arguments:
    * df:pandas.DataFrame, dataframe to use as data for plotting.
    * group_identifiers:list[str], Rows with the same group_identifiers values will be plot as a line.
    * x_axis_col:str/list[str], column(s) to use as x-axis value(s) for each line. If a list of length 2 is provided, then a 3D plot is used.
    * y_axis_col:str/list[str], column(s) to use as left y-axis value for each line. If a list is provided, then subplots_identifiers will be ignored; subplots are created for each y-axis column instead.

    Optional arguments:
    * subplots_identifiers:list[str], if provided, then subplots for each subset of unique values of the identifiers will be created, with the group identifiers applied for each.
    * subplots_df_modifier:(df: DataFrame) -> DataFrame, if provided, then apply this function per DataFrame group as partitioned by subplots_identifiers. Default: None
    * y_axis_col_secondary:str, if provided, then a new line is created with this as right y-axis value. Default: None
    * *_axis_label*:str, provide the label to use for each axis. If None is provided, then it defaults to the column name. Default: None
    * subplot_size_inches:(int, int), size of each subplot, in inches. Default: (6, 4)
    * save_name:str, if provided, then plot image is saved at the provided path; else the result is just displayed. Default: None
    * short_labels:dict[str, str], if provided, then labels are created using the provided <key>: <value to use>; or else keys will be truncated to the first 3 characters by default.
    * plot_type_2d:['line', 'bar'], determines what plots are generated for 2D plots: (Default: 'bar')
        - 'line': each group is plotted as a line of different color.
        - 'bar': for each x-axis value, each group has a bar chart starting from 0, of a different color. Will void y_axis_col_secondary.
    * group_order:list[any], the order in which to present grouped 'bar' data in, from left to right. Only valid for 1 group identifier. Default: None, i.e., any order works.
    * normalized_y_axes:list[str], y-axis subplots that are normalized plots, and should have a dotted line marking 1.0. Default: empty list.
    """
    # Sanity checks
    if x_axis_label is not None and type(x_axis_label) is not type(x_axis_col):
        raise ValueError("Type mismatch between x_axis_label and x_axis_col! Either define both as str or list[str].")
    if isinstance(x_axis_label, list) and len(x_axis_label) != len(x_axis_col):
        raise ValueError("Length mismatch between x_axis_label and x_axis_col!")
    if y_axis_label is not None and type(y_axis_label) is not type(y_axis_col):
        raise ValueError("Type mismatch between y_axis_label and y_axis_col! Either define both as str or list[str].")
    if isinstance(y_axis_label, list) and len(y_axis_label) != len(y_axis_col):
        raise ValueError("Length mismatch between y_axis_label and y_axis_col!")
    if not group_order is None and len(group_identifiers) > 1:
        raise ValueError("group_order can only be specified for group_identifiers of size 1!")

    # Convenience function for labelling
    def get_identifiers_label(identifiers: list[str], values: list[str] = None, df: pd.DataFrame = None) -> str:
        assert values is not None or df is not None

        if values is None:
            values = [df[id].unique()[0] for id in identifiers]
        
        def get_id(id):
            default_id = id[:3]
            if short_labels is None:
                return default_id
            
            return short_labels.get(id, default_id)
        
        return ",".join([f"{get_id(id)}={val}" for id, val in zip(identifiers, values)])

    # Set up labels
    if x_axis_label is None:
        x_axis_label = x_axis_col
    if y_axis_label is None:
        y_axis_label = y_axis_col
    if y_axis_col_secondary is not None and y_axis_label_secondary is None:
        y_axis_label_secondary = y_axis_col_secondary

    # check for 3D
    is_3d = False
    if isinstance(x_axis_col, list):
        x_axis_len = len(x_axis_col)
        if x_axis_len > 2 or x_axis_len < 1:
            raise ValueError("List must be length 1 or 2!")
        if y_axis_col_secondary is not None:
            raise ValueError("Secondary y-axis is not supported with 3D graphs!")
        
        if x_axis_len == 1:
            x_axis_col = x_axis_col[0]
            x_axis_label = x_axis_label[0]
        else:
            is_3d = True

    # check for bar plot
    is_bar = not is_3d and (plot_type_2d == 'bar')

    # Set up figure and axes
    fig_w, fig_h = subplot_size_inches
    main_fig = plt.figure(constrained_layout=not is_3d)
    subplot_figs = []
    subplot_dfs = []
    rows, cols = 1, 1

    is_y_axis_subplot = isinstance(y_axis_col, list)
    is_identifier_subplot = subplots_identifiers is not None
    
    if is_y_axis_subplot:
        rows, cols = get_portrait_square(len(y_axis_col))
        
        def constant_df_iterator():
            for i in range(len(y_axis_col)):
                yield df if subplots_df_modifier is None else subplots_df_modifier(df)
        subplot_dfs = constant_df_iterator()
        
    elif is_identifier_subplot:
        # get unique counts
        unique_counts = sorted([(id, df[id].unique().shape[0]) for id in subplots_identifiers], key=lambda p: p[1], reverse=True)
        
        for _, y in df.groupby(subplots_identifiers, as_index=False):
            subplot_dfs.append(y if subplots_df_modifier is None else subplots_df_modifier(y))
        subplot_dfs = sorted(subplot_dfs, key=lambda d: tuple([d[p[0]].unique()[0] for p in unique_counts]))
        subplot_count = len(subplot_dfs)

        # create subplots
        rows, cols = get_portrait_square(subplot_count)
        if len(subplots_identifiers) > 1:
            rows = unique_counts[0][-1] # use largest unique count as row count
            cols = subplot_count // rows
    else:
        # make single axes by default
        subplot_dfs = [df if subplots_df_modifier is None else subplots_df_modifier(df)]
        subplot_figs = [main_fig]
    
    # make subfigures and resize (if required)
    if is_y_axis_subplot or is_identifier_subplot:
        main_fig.set_size_inches(fig_w * cols, fig_h * rows)
        subplot_figs = main_fig.subfigures(rows, cols, width_ratios=[1 for _ in range(cols)], height_ratios=[1 for _ in range(rows)])

    # Convert group column into categorical to preserve order, if needed.
    if not group_order is None:
        df[group_identifiers[0]] = pd.Categorical(df[group_identifiers[0]], categories=group_order, ordered=True)

    # Get all unique group permutations.
    unique_groups = df.value_counts(group_identifiers).index.tolist()
    num_unique_groups = len(unique_groups)

    # Set up markers and colors
    markers = USABLE_MARKERS.copy()
    shuffle(markers)
    markers = cycle(markers)
    colors = cycle(cm.rainbow(np.linspace(0, 1, len(unique_groups))))

    # Set up y-axis legends only if necessary
    legend_handles = []
    if y_axis_col_secondary is not None:
        legend_handles.append(Line2D([0], [0], color='black', label=y_axis_label))
        legend_handles.append(Line2D([0], [0], color='black', linestyle='dotted', label=y_axis_label_secondary))
    
    # set colors and markers for all combinations of group identifiers used across all subplots.
    attr_map = {}
    for combi in unique_groups:
        # grab next available color and marker
        marker = next(markers)
        color = next(colors)

        # add to map
        attr_map[combi] = marker, color

        # add legend handle
        legend_line = Line2D(
            [0], [0], 
            color=color, marker=marker,
            label=get_identifiers_label(group_identifiers, list(combi))
        )
        legend_handles.append(legend_line)

    # get the offsets if using 'bar' mode
    bar_width = 0.8 / num_unique_groups
    bar_offsets = [(2*i + 1 - num_unique_groups) * bar_width / 2 for i in range(num_unique_groups)]

    # function to remove all axes legends
    def remove_legend(ax: Axes):
        if ax is None:
            return
        legend = ax.get_legend()
        if legend is None:
            return
        legend.remove()

    for fig_i, (df, fig) in enumerate(zip(subplot_dfs, subplot_figs.flat)):
        # add y-axis subplot support
        ycol = y_axis_col[fig_i] if is_y_axis_subplot else y_axis_col
        ylabel = y_axis_label[fig_i] if is_y_axis_subplot else y_axis_label

        if is_y_axis_subplot:
            fig.suptitle(ylabel)
        elif is_identifier_subplot:
            fig.suptitle(get_identifiers_label(subplots_identifiers, df=df))

        # Split DataFrame into distinct groups 
        groups = [y for _, y in df.groupby(group_identifiers, as_index=False, observed=False)]

        if is_3d:
            # 3D subplot case
            rows, cols = get_portrait_square(len(groups))
            axes = fig.subplots(nrows=rows, ncols=cols, subplot_kw=dict(projection='3d'))
        
            for grp, ax_i in zip(groups, np.ndindex(axes.shape)):
                # get axes and color
                ax = axes[ax_i]
                _, color = attr_map[tuple(grp[col].unique()[0] for col in group_identifiers)]

                # get bar values
                grp.sort_values(by=x_axis_col, inplace=True)
                xy_labels = [grp[col].unique() for col in x_axis_col]
                xy_plane = [np.arange(x.shape[0]) for x in xy_labels]
                ypos, xpos = np.meshgrid(*xy_plane)
                xpos = xpos.flatten()
                ypos = ypos.flatten()
                top = grp[ycol].values.ravel()
                bottom = np.zeros_like(top)

                # plot bar
                ax.bar3d(xpos.flatten(), ypos.flatten(), bottom, .5, .5, top, shade=True, color=color)
                
                # set ticks
                ax.set_xticks(xy_plane[0] + .25)
                ax.set_yticks(xy_plane[1] + .25)
                ax.set_xticklabels(xy_labels[0])
                ax.set_yticklabels(xy_labels[1])
                
                # set axes labels
                ax.set_xlabel(x_axis_label[0])
                ax.set_ylabel(x_axis_label[1])
                ax.set_zlabel(ylabel)

                # set aspect ratio
                ax.set_box_aspect(fig_w/fig_h)

                remove_legend(ax)
        else:
            # Normal group plot
            ax = fig.add_subplot(111)
            ax2 = None
            if y_axis_col_secondary is not None:
                ax2 = ax.twinx()

            # Get x-axis count
            x_axis_count = df[x_axis_col].nunique()
            bar_x = np.arange(x_axis_count)

            # Get min and max y values for ylim scaling
            y_min = math.inf
            y_max = -math.inf

            # check normalized
            is_norm = ycol in normalized_y_axes
            for grp_i, grp in enumerate(groups):
                marker, color = attr_map[tuple(grp[col].unique()[0] for col in group_identifiers)]

                # sort group by x-axis
                grp.sort_values(by=[x_axis_col], inplace=True)

                # update ylims
                y_vals = grp[ycol].tolist()
                y_min = min(y_min, min(y_vals))
                y_max = max(y_max, max(y_vals))
                
                if is_bar:
                    ax.bar(bar_x + bar_offsets[grp_i], y_vals, bar_width, color=color)
                else:
                    grp.plot(x=x_axis_col, y=ycol, kind='line', linestyle='solid', marker=marker, color=color, ax=ax)
                    if y_axis_col_secondary is not None:
                        grp.plot(x=x_axis_col, y=y_axis_col_secondary, kind='line', linestyle='dotted', marker=marker, color=color, ax=ax2)

            # set ylims
            ylim_diff = 0.2*(y_max-y_min)
            ylim_bottom = y_min - ylim_diff
            if y_min >= 0:
                ylim_bottom = max(0, ylim_bottom) # avoid floating bars
            ylim_top = y_max + ylim_diff
            if is_norm:
                ylim_bottom = max(0, ylim_bottom) if ylim_bottom < 1 else min(0.95, ylim_bottom) # clamp to 0/0.95
                ylim_top = max(1.05, ylim_top) # clamp to 1.05
            ax.set_ylim(bottom=ylim_bottom, top=ylim_top)

            # add normalization line
            if is_norm:
                ax.axhline(1, linestyle='--', color='black')

            # set ticks (if bar)
            if is_bar:
                ax.set_xticks(bar_x, sorted(df[x_axis_col].unique().tolist()))
            
            # set labels
            ax.set_xlabel(xlabel=x_axis_label)
            if is_y_axis_subplot:
                ax.yaxis.get_label().set_visible(False)
            else:
                ax.set_ylabel(ylabel=ylabel)
            if ax2 is not None:
                ax2.set_ylabel(ylabel=y_axis_label_secondary)

            remove_legend(ax)
            remove_legend(ax2)

    # set up legend
    main_fig.legend(handles=legend_handles, loc='center left', bbox_to_anchor=(1, 0.5))
    if is_3d:
        main_fig.tight_layout()
    if save_path is not None:
        main_fig.savefig(save_path, bbox_inches='tight', dpi=600)
    plt.close()