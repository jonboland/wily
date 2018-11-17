"""
Compares metrics between uncommitted files and indexed files
"""
import tabulate

import os
import wily.cache as cache
from wily import logger
from wily.config import DEFAULT_GRID_STYLE
from wily.operators import (
    resolve_metric,
    resolve_operator,
    get_metric,
    GOOD_COLORS,
    BAD_COLORS,
    OperatorLevel,
)


def diff(config, files, metrics, changes_only=True, detail=True):
    """
    Show the differences in metrics for each of the files.

    :param config: The wily configuration
    :type  config: :namedtuple:`wily.config.WilyConfig`


    """
    archiver = config.archiver
    config.targets = files
    files = list(files)
    if cache.has_index(config, archiver):
        index = cache.get_index(config, archiver)
        last_revision = index[0]
    else:
        raise RuntimeError("Missing index, run `wily build`.")

    # Convert the list of metrics to a list of metric instances
    operators = {resolve_operator(metric.split(".")[0]) for metric in metrics}
    metrics = [(metric.split(".")[0], resolve_metric(metric)) for metric in metrics]
    data = {}
    results = []

    # Build a set of operators
    _operators = [operator.cls(config) for operator in operators]

    cwd = os.getcwd()
    os.chdir(config.path)
    for operator in _operators:
        logger.debug("Running {0} operator".format(operator.name))
        data[operator.name] = operator.run(None, config)
    os.chdir(cwd)
    # Write a summary table..
    last_entry = cache.get(config, archiver, last_revision["revision"])
    extra = []
    for operator, metric in metrics:
        if detail and resolve_operator(operator).level == OperatorLevel.Object:
            for file in files:
                try:
                    extra.extend(
                        [
                            "{0}:{1}".format(file, k)
                            for k in data[operator][file].keys()
                            if k != metric.name
                        ]
                    )
                except KeyError:
                    logger.debug("File {0} not in cache".format(file))
                    logger.debug("Cache follows -- ")
                    logger.debug(data[operator])
    files.extend(extra)
    logger.debug(files)
    for file in files:
        try:
            metrics_data = []
            has_changes = False
            for operator, metric in metrics:
                try:
                    current = get_metric(
                        last_entry["operator_data"], operator, file, metric.name
                    )
                except KeyError as e:
                    current = "-"
                try:
                    new = get_metric(data, operator, file, metric.name)
                except KeyError as e:
                    new = "-"
                if new != current:
                    has_changes = True
                if metric.type in (int, float) and new != "-" and current != "-":
                    if current > new:
                        metrics_data.append(
                            "{0:n} -> \u001b[{2}m{1:n}\u001b[0m".format(
                                current, new, BAD_COLORS[metric.measure]
                            )
                        )
                    elif current < new:
                        metrics_data.append(
                            "{0:n} -> \u001b[{2}m{1:n}\u001b[0m".format(
                                current, new, GOOD_COLORS[metric.measure]
                            )
                        )
                    else:
                        metrics_data.append("{0:n} -> {1:n}".format(current, new))
                else:
                    if current == "-" and new == "-":
                        metrics_data.append("-")
                    else:
                        metrics_data.append("{0} -> {1}".format(current, new))
            if has_changes or not changes_only:
                results.append((file, *metrics_data))
            else:
                logger.debug(metrics_data)
        except KeyError as e:
            logger.debug("Could not find {0}".format(e))

    descriptions = [metric.description for operator, metric in metrics]
    headers = ("File", *descriptions)
    if len(results) > 0:
        print(
            # But it still makes more sense to show the newest at the top, so reverse again
            tabulate.tabulate(
                headers=headers, tabular_data=results, tablefmt=DEFAULT_GRID_STYLE
            )
        )
