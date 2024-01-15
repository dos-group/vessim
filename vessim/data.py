import os
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import Optional, List, Union, Dict
from zipfile import ZipFile

import pandas as pd

from vessim._util import DatetimeLike, PandasObject

VESSIM_DATASETS = {
    "solcast2022_germany": {
        "actual": "solcast2022_germany_actual.csv",
        "forecast": "solcast2022_germany_forecast.csv",
        "fill_method": "bfill",
        "static_forecast": False,
        "url": "https://raw.githubusercontent.com/dos-group/vessim/solcast_data/datasets/solcast2022_germany.zip",
    },
    "solcast2022_global": {
        "actual": "solcast2022_global_actual.csv",
        "forecast": "solcast2022_global_forecast.csv",
        "fill_method": "bfill",
        "static_forecast": False,
        "url": "https://raw.githubusercontent.com/dos-group/vessim/solcast_data/datasets/solcast2022_global.zip",
    },
}


def _load_dataset(
    dataset: str,
    scale: float = 1.0,
    start_time: Optional[DatetimeLike] = None,
    use_forecast: bool = False,
) -> Dict:
    """Downloads a dataset from the vessim repository, unpacks it and loads data."""
    if dataset not in VESSIM_DATASETS:
        raise ValueError(f"Dataset '{dataset}' not found. Available datasets are: "
                         f"{', '.join(list(VESSIM_DATASETS.keys()))}")

    dataset_config = VESSIM_DATASETS[dataset]
    required_files = [dataset_config["actual"]]
    if use_forecast:
        required_files.append(dataset_config["forecast"])

    dir_path = Path().expanduser().resolve()

    if not _check_files(required_files, dir_path):
        print("Required data files not present locally. Try downloading...")
        os.makedirs(dir_path, exist_ok=True)
        zip_path = dir_path / "dataset.zip"
        try:
            urllib.request.urlretrieve(dataset_config["url"], zip_path)
        except Exception:
            raise RuntimeError(f"Dataset could not be retrieved from url: "
                               f"{dataset_config['url']}")

        with ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(path=dir_path)
        os.remove(zip_path)
        print("Successfully downloaded and unpacked data files.")

    actual = _read_data_from_csv(
        dir_path / dataset_config["actual"], index_cols=[0], scale=scale
    )

    forecast: Optional[PandasObject] = None
    if use_forecast:
        if dataset_config.get("static_forecast", False):
            # There is only one timestamp present in the forecast (static forecast)
            index_cols: List[int] = [0]
        else:
            # There are two timestamps present in the forecast (non-static forecast)
            index_cols = [0, 1]

        forecast = _read_data_from_csv(
            dir_path / dataset_config["forecast"], index_cols=index_cols, scale=scale
        )

    if start_time is not None:
        shift = pd.to_datetime(start_time) - actual.index[0]
        print(f"Data is being shifted by {shift}")
        actual.index += shift
        if use_forecast:
            forecast = _shift_dataframe(forecast, shift)  # type: ignore

    return dict(
        actual=actual,
        forecast=None if not use_forecast else forecast,
        fill_method=dataset_config.get("fill_method", "ffill"),
    )


def _check_files(files: List[str], base_dir: Path) -> bool:
    """Check whether files are present in specified base directory."""
    for file in files:
        path = os.path.join(base_dir, file)
        if not os.path.isfile(path):
            return False
    return True


def _read_data_from_csv(
    path: Path, index_cols: List[int], scale: float = 1.0
) -> PandasObject:
    """Retrieves a dataframe from a csv file and transforms it."""
    df = _convert_to_datetime(pd.read_csv(path, index_col=index_cols))
    return (df * scale).astype(float)


def _convert_to_datetime(df: PandasObject) -> PandasObject:
    """Converts the indices of a dataframe to datetime indices."""
    if isinstance(df.index, pd.MultiIndex):
        index: pd.MultiIndex = df.index
        for i, level in enumerate(index.levels):
            index = index.set_levels(pd.to_datetime(level), level=i)
        df.index = index
    else:
        df.index = pd.to_datetime(df.index)

    df.sort_index(inplace=True)
    return df


def _shift_dataframe(df: PandasObject, shift: timedelta) -> PandasObject:
    """Shifts indices of the given DataFrame by a timedelta."""
    if isinstance(df.index, pd.MultiIndex):
        index: pd.MultiIndex = df.index
        for i, level in enumerate(index.levels):
            index = index.set_levels(level + shift, level=i)
        df.index = index
    else:
        df.index += shift
    return df
