import os
import urllib.request
from pathlib import Path
from zipfile import ZipFile
from typing import Optional, List, Union, Tuple
from datetime import datetime, timedelta

import pandas as pd


Column = Union[int, str]
DatetimeLike = Union[str, datetime]
PandasObject = Union[pd.Series, pd.DataFrame]


def load_dataset(
    dataset: str,
    data_dir: Optional[Union[str, Path]] = None,
    scale: float = 1.0,
    start_time: Optional[DatetimeLike] = None,
    use_forecast: bool = True,
) -> Tuple[PandasObject, Optional[PandasObject]]:
    """Downloads a dataset from the vessim repository, unpacks it and loads data.

    If all files are already present in the directory, the download is skipped.

    Args:
        dataset: Name of the dataset to be downloaded.
        data_dir: Optional absolute or relative path to the directory where data should
            be loaded into. Defaults to None.
        scale: Multiplies all data point with a value. Defaults to 1.0.
        start_time: Shifts the data so that it starts at this timestamp if specified.
            Defaults to None.
        use_forecast: Boolean indicating if forecast should be loaded. Default is true.

    Returns:
        Dataframes containing actual and forecasted data to be fed into a TimeSeriesAPI.

    Raises:
        RuntimeError if dataset can not be loaded.
    """
    files = [f"{dataset}_actual.csv", f"{dataset}_forecast.csv"]
    dir_path = Path(data_dir or "").expanduser().resolve()

    if _check_files(files, dir_path):
        print("Files already downloaded")
    else:
        if not dir_path.is_dir():
            os.makedirs(dir_path)
        try:
            url = f"https://raw.githubusercontent.com/dos-group/vessim/solcast_data/datasets/{dataset}.zip"
            urllib.request.urlretrieve(url, dir_path / f"{dataset}.zip")
        except Exception:
            raise RuntimeError(f"Dataset '{dataset}' could not be retrieved")

        with ZipFile(dir_path / f"{dataset}.zip", "r") as zip_ref:
            zip_ref.extractall(path=dir_path)
        os.remove(dir_path / f"{dataset}.zip")

    actual = read_data_from_csv(dir_path / files[0], index_cols=[0], scale=scale)

    if start_time is None:
        shift = None
    else:
        shift = pd.to_datetime(start_time) - actual.index[0]
        # TODO shift is already in read_data_from_csv. There is probably a better way to
        # shift both dataframes by the exact same amount given the start_time
        actual.index += shift

    forecast: Optional[PandasObject] = None
    if use_forecast:
        forecast = read_data_from_csv(
            dir_path / files[1], index_cols=[0, 1], scale=scale, shift=shift
        )

    return actual, forecast


def _check_files(files: List[str], base_dir: Path) -> bool:
    """Check whether files are present in specified base directory."""
    for file in files:
        path = os.path.join(base_dir, file)
        if not os.path.isfile(path):
            return False
    return True


def read_data_from_csv(
    path: Path,
    index_cols: Union[Column, List[Column]],
    scale: float = 1.0,
    shift: Optional[Union[str, pd.DateOffset, timedelta]] = None,
) -> PandasObject:
    """Retrieves a dataframe from a csv file and transforms it.

    Args:
        path: Path to the csv file containing the data.
        index_cols: Name or index of the columns containing the timestamps in data file.
        scale: Multiplies all data point with a value. Defaults to 1.0.
        shift: Shifts the indices by a specific offset.

    Returns:
        Scaled and shifted dataframe retrieved from csv file.
    """
    df = convert_to_datetime(pd.read_csv(path, index_col=index_cols))
    if shift is not None:
        if isinstance(df.index, pd.MultiIndex):
            index: pd.MultiIndex = df.index
            for i, level in enumerate(index.levels):
                index = index.set_levels(level + shift, level=i)
            df.index = index
        else:
            df.index += shift

    return (df * scale).astype(float)


def convert_to_datetime(df: PandasObject) -> PandasObject:
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
