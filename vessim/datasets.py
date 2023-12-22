import os
import urllib.request
from pathlib import Path
from zipfile import ZipFile
from typing import Optional, Callable, List, Union, Dict

import pandas as pd

Column = Union[int, str]

Datasets: Dict[str, Dict] = {
    "solcast2022_germany": {
        "actual": "solcast2022_germany_actual.csv",
        "forecast": "solcast2022_germany_forecast_1h.csv",
    },
    "solcast2022_global": {
        "actual": "solcast2022_global_actual.csv",
        "forecast": "solcast2022_global_forecast_1h.csv",
    }
}


def read_data_from_csv(
    path: Path,
    index_cols: Union[Column, List[Column]],
    value_cols: Optional[List[Column]] = None,
    scale: float = 1.0,
    transform: Optional[Callable] = None,
    **kwargs,
) -> Union[pd.Series, pd.DataFrame]:
    """Retrieves a dataframe from a csv file and transforms it.

    Args:
        path: Path to the csv file containing the data.
        index_cols: The name or index of the column with the timestamps in data file.
            In special cases (if some more index columns are needed for transforming),
            there can be more than column specified.
        value_cols: Optional list of columns that contain the desired data.
            If not specified, every column except the index is treated as a data column.
        scale: Multiplies all data point with a value. Defaults to 1.0.
        transform: Optional function transforming the data in a custom way after the data
            is read and before scaling (e.g resampling, reindexing).
        **kwargs: Optional keyword arguments which can be used in the transform
            function (e.g resampling options).
    """
    data = pd.read_csv(path, index_col=index_cols, parse_dates=True)
    if value_cols is not None:
        data = data[value_cols]
    if transform is not None:
        data = transform(data, **kwargs)
    return (data * scale).astype(float)


def load_dataset(dataset: str, data_dir: Path) -> Dict[str, str]:
    """Downloads a dataset from the vessim repository and unpacks it.

    If all files are already present in the directory, the download is skipped.

    Args:
        dataset: Name of the dataset to be downloaded.
        data_dir: Absolute path to directory in which the data should be located.

    Returns:
        Dictionary of data types with their respective file names.

    Raises:
        RuntimeError if dataset can not be loaded.
    """
    files = list(Datasets[dataset].values())

    if check_files(files, data_dir):
        print("Files already downloaded")
    else:
        if not data_dir.is_dir():
            os.makedirs(data_dir)
        try:
            file_name = f"{dataset}.zip"
            path = data_dir / file_name
            url = f"https://raw.githubusercontent.com/dos-group/vessim/solcast_data/datasets/{file_name}"
            urllib.request.urlretrieve(url, path)
        except Exception:
            raise RuntimeError(f"Dataset '{dataset}' could not be retrieved")

        with ZipFile(path, "r") as zip_ref:
            zip_ref.extractall(path=os.path.dirname(path))
        os.remove(path)

    return Datasets[dataset]


def check_files(files: List[str], base_dir: Path) -> bool:
    """Check whether files are present in specified base directory.

    Args:
        files: Names of files to be checked.
        base_dir: The directory in which the files should be present.

    Returns:
        True if all files are present and False otherwise.
    """
    for file in files:
        path = os.path.join(base_dir, file)
        if not os.path.isfile(path):
            return False
    return True
