import os
import urllib.request
from pathlib import Path
from zipfile import ZipFile
from typing import Optional, Callable, List, Union, Dict, Tuple

import pandas as pd

Column = Union[int, str]
PathLike = Union[str, Path]

datasets: Dict[str, Dict] = {
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
    path: PathLike,
    index_cols: Union[Column, List[Column]],
    value_cols: Optional[List[Column]] = None,
    scale: float = 1.0,
    offset: float = 0.0,
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
        offset: Adds a value to all data points. Defaults to 0.0.
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
    return (data * scale + offset).astype(float)


def download_dataset(
    dataset: str, data_dir: Optional[str] = None
) -> Tuple[Path, Dict[str, str]]:
    """Downloads a dataset from the vessim repository and unpacks it.

    If all files are already present in the directory, the download is skipped.

    Args:
        dataset: Name of the dataset to be downloaded.
        data_dir: Directory in which the data should be located.

    Returns:
        Absolute path to the directory where the data is now located.
        Dictionary of data types with their respective file names.

    Raises:
        ValueError if dataset is not available.
        RuntimeError if dataset can not be downloaded.
    """
    if dataset not in datasets.keys():
        raise ValueError("Dataset '{dataset}' is not available.")

    dir_path = Path(data_dir or "").expanduser().resolve()
    files = list(datasets[dataset].values())

    if check_files(files, dir_path):
        print("Files already downloaded")
    else:
        if not dir_path.is_dir():
            os.makedirs(dir_path)
        try:
            file_name = f"{dataset}.zip"
            path = dir_path / file_name
            url = f"https://raw.githubusercontent.com/dos-group/vessim/solcast_data/datasets/{file_name}"
            urllib.request.urlretrieve(url, path)
        except Exception:
            raise RuntimeError(f"Dataset '{dataset}' could not be retrieved")

        unzip_file(path)

        if check_files(files, dir_path):
            print(f"Dataset downloaded successfully to '{path}'")

    return dir_path, datasets[dataset]


def check_files(files: List[str], base_dir: PathLike) -> bool:
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


def unzip_file(
    path: PathLike, to: Optional[PathLike] = None, remove_finished: bool = False
) -> None:
    """Unzips a given zip-file into the base directory.

    Args:
        path: Path to the zip file.
        to: Path to the directory where the zip file should be extracted to.
            If None, then the zip file is extracted in the same directory.
        remove_finished: Boolean indicating whether the zipped file should be deleted
            after files are extracted.
    """
    if to is None:
        to = os.path.dirname(path)
    with ZipFile(path, "r") as zip_ref:
        zip_ref.extractall(path=to)
    if remove_finished:
        os.remove(path)
