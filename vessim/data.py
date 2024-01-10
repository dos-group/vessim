import os
import urllib.request
from pathlib import Path
from zipfile import ZipFile
from typing import Optional, List, Union, Tuple, Dict, Literal
from datetime import datetime, timedelta

import pandas as pd


DatetimeLike = Union[str, datetime]
PandasObject = Union[pd.Series, pd.DataFrame]


Datasets: Dict[str, Dict] = {
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


def load_dataset(
    dataset: Union[str, Dict],
    data_dir: Path,
    scale: float = 1.0,
    start_time: Optional[DatetimeLike] = None,
    use_forecast: bool = True,
) -> Tuple[PandasObject, Optional[PandasObject], Literal["ffill", "bfill"]]:
    """Downloads a dataset from the vessim repository, unpacks it and loads data.

    If all files are already present in the directory, the download is skipped.

    Args:
        dataset: If a string is provided, the TimeSeriesApi is loaded from one of the
            vessim datasets. Currently available datasets are:
                `solcast2022_germany` and `solcast2022_global`
            Otherwise, it should be a Dictionary containing info about the dataset
            with following entries:
                `actual`: Name of the file containing the actual data.
                `forecast`: Name of the file containing the forecasted data. This is
                    not needed if use_forecast is set to False.
                `fill_method`: The fill_method of the TimeSeriesApi. If not specified,
                    `bfill` is used.
                `static_forecast`: Bool indicating if the forecast is static. If set
                    to True, the forecast does not contain a `Request Timestamp`, but
                    if not specified, the forecast is treated as non-static forecast.
                    This is not needed if use_forecast is set to False.
                `url`: String with a URL to a zip-file if data not locally available.
        data_dir: Absolute path to the directory where the data is/should be located.
        scale: Multiplies all data points with a value. Defaults to 1.0.
        start_time: Shifts the data so that it starts at this timestamp if specified.
            Defaults to None.
        use_forecast: Bool indicating if forecast should be loaded. Default is true.

    Returns:
        The dataframe of actual data, the optional dataframe of forecast data and the
        fill_method to be fed into a TimeSeriesApi.

    Raises:
        RuntimeError if dataset can not be loaded.
    """
    if isinstance(dataset, str):
        dataset_dict: Dict = Datasets[dataset]
    else:
        dataset_dict = dataset

    required_files = [dataset_dict["actual"]]
    if use_forecast:
        required_files.append(dataset_dict["forecast"])

    dir_path = Path(data_dir or "").expanduser().resolve()

    if not _check_files(required_files, dir_path):
        if "url" not in dataset_dict.keys():
            raise RuntimeError("Data files could not be found.")

        print("Required data files not present. Try downloading...")
        os.makedirs(dir_path, exist_ok=True)

        try:
            urllib.request.urlretrieve(dataset_dict["url"], dir_path / "dataset.zip")
        except Exception:
            raise RuntimeError(
                f"Dataset could not be retrieved from url: {dataset_dict['url']}"
            )

        with ZipFile(dir_path / "dataset.zip", "r") as zip_ref:
            zip_ref.extractall(path=dir_path)
        os.remove(dir_path / "dataset.zip")
        print("Successfully downloaded and unpacked data files.")

    actual = _read_data_from_csv(
        dir_path / dataset_dict["actual"], index_cols=[0], scale=scale
    )

    forecast: Optional[PandasObject] = None
    if use_forecast:
        if dataset_dict.get("static_forecast", False):
            # There is only one timestamp present in the forecast (static forecast)
            index_cols: List[int] = [0]
        else:
            # There are two timestamps present in the forecast (non-static forecast)
            index_cols = [0, 1]

        forecast = _read_data_from_csv(
            dir_path / dataset_dict["forecast"], index_cols=index_cols, scale=scale
        )

    if start_time is not None:
        shift = pd.to_datetime(start_time) - actual.index[0]
        actual.index += shift
        if use_forecast:
            forecast = _shift_dataframe(forecast, shift) # type: ignore

    return actual, forecast, dataset_dict.get("fill_method", "bfill")


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
    df = convert_to_datetime(pd.read_csv(path, index_col=index_cols))
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
