import os
import hashlib
import urllib.request
from zipfile import ZipFile
from typing import Optional, Callable, Literal, List, Union, Dict

import pandas as pd
from vessim import TimeSeriesApi

Column = Union[int, str]


class DataLoader:
    """Base class for loading and unpacking data.

    Args:
        base_dir: Absolute path to the directory where the data is/ should be located.
        download: Boolean indicating whether the downloading of data should be handled.
            This base class does not provide any functionality regarding downloading, but
            subclasses should override the download function in case that the data is
            available on the internet or elsewhere.
    """

    def __init__(self, base_dir: str, download: bool = False):
        self._base_dir = base_dir

        if download:
            # Create new directory if it does not already exist
            if not (os.path.exists(base_dir) and os.path.isdir(base_dir)):
                os.makedirs(base_dir)
            self.download()

    def download(self) -> None:
        """Base method for automatic download of data. Should be overridden."""
        raise NotImplementedError()

    def get_time_series_api(
        self,
        actual_file_name: str,
        actual_index_cols: Union[Column, List[Column]],
        actual_value_cols: Optional[List[Column]] = None,
        actual_transform: Optional[Callable] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
        forecast_file_name: Optional[str] = None,
        forecast_index_cols: Optional[Union[Column, List[Column]]] = None,
        forecast_value_cols: Optional[List[Column]] = None,
        forecast_transform: Optional[Callable] = None,
        **kwargs,
    ) -> TimeSeriesApi:
        """Method for extracting an initialized TimeSeriesApi from the data.

        Args:
            actual_file_name: The name of the csv file containing the actual data.
            actual_index_cols: The name of the column with the timestamps in data file.
                In special cases (if some more index columns are needed for transforming),
                there can be more than column name specified.
            actual_value_cols: Optional list of names of the data columns that contain the
                desired data. If not specified, every column except the index is treated
                as a data column.
            actual_transform: Optional function transforming the actual data in a custom
                way after the data is read in (e.g resampling, reindexing, scaling).
            fill_method: The way in which holes are filled in the actual data. Can be
                either `ffill` or `bfill`. Defaults to `ffill`. More information on the
                fill_method is provided in the TimeSeriesApi class.
            forecast_file_name: Optional name of csv file containing forecast data. Only
                used if forecast is available.
            forecast_index_cols: Optional column names of the indices of forecast data.
                This needs to be specified if forecast is available. Depending on the data
                format, this should be either one or two columns except more columns are
                needed for data transformation.
            forecast_value_cols: Optional column names of data columns. If not specified,
                every column except the index is treated as a data column.
            forecast_transform: Optional function transforming forecast data in a custom
                way after the data is read in (e.g resampling, reindexing, scaling).
            **kwargs: Optional keyword arguments which can be used in the transform
                function (e.g scaling factors).

        Returns:
            Initialized TimeSeriesApi that allows queries of actual data and forecast data
        """
        actual = self.read_data_from_csv(
            actual_file_name,
            actual_index_cols,
            actual_value_cols,
            actual_transform,
            **kwargs,
        )
        forecast: Optional[Union[pd.Series, pd.DataFrame]] = None
        if forecast_file_name is not None:
            forecast = self.read_data_from_csv(
                forecast_file_name,
                forecast_index_cols,
                forecast_value_cols,
                forecast_transform,
                **kwargs,
            )
        return TimeSeriesApi(actual, forecast, fill_method)

    def read_data_from_csv(
        self,
        file: str,
        index_cols: Optional[Union[Column, List[Column]]],
        value_cols: Optional[List[Column]],
        transform: Optional[Callable],
        **kwargs,
    ) -> Union[pd.Series, pd.DataFrame]:
        """Helper function to read in a csv file and transforming it."""
        data = pd.read_csv(
            os.path.join(self._base_dir, file), index_col=index_cols, parse_dates=True
        )
        if value_cols is not None:
            data = data[value_cols]
        if transform is not None:
            data = transform(data, **kwargs)
        return data.astype(float)

    def unzip_file(self, zip_file: str, remove_finished: bool = False) -> None:
        """Unzips a given zip-file into the base directory.

        Args:
            zip_file: Relative path from the base_directory to the zip file that should
                be extracted. The file must be located within the base directory.
            remove_finished: Boolean indicating whether the zipped file should be deleted
                after files are extracted.
        """
        path = os.path.join(self._base_dir, zip_file)
        with ZipFile(path, "r") as zip_ref:
            zip_ref.extractall(path=self._base_dir)
        if remove_finished:
            os.remove(path)

    def check_integrity(
        self,
        files: List[str],
        file_checksums: Dict[str, str] = {},
        hash_algorithm: str = "md5",
        block_size: int = 65536,
    ) -> bool:
        """Check whether files are present in base directory and valid.

        Args:
            files: Names of files to be checked.
            file_checksums: Dictionary of files with their respective checksums. For every
                file in the dictionary, the integrity is checked.
            hash_algorithm: Type of hashing method used for checksum. Defaults to `md5`.
            block_size: Determines amount of data read at once. Defaults to 65536 bytes.

        Returns:
            True if all files are present and valid and False otherwise.
        """
        for file in files:
            path = os.path.join(self._base_dir, file)
            if not os.path.isfile(path):
                return False

            # Check if checksum is invalid
            if file in file_checksums.keys():
                checksum = self._calculate_checksum(file, hash_algorithm, block_size)
                if checksum != file_checksums[file]:
                    return False
        return True

    def _calculate_checksum(self, file: str, hash_algorithm: str, block_size: int) -> str:
        """Calculate the checksum of a given file depending on specific hash algorithm."""
        hasher = hashlib.new(hash_algorithm)
        with open(os.path.join(self._base_dir, file), "rb") as f:
            buf = f.read(block_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(block_size)
        return hasher.hexdigest()



class SolcastDataLoader(DataLoader):
    """DataLoader for Solcast Dataset extracted from."""
    _url =  ""
    _file_name = "solcast2022_1h.zip"
    _checksums: Dict[str, str] = {
        "solcast2022_germany_actual.csv": "",
        "solcast2022_germany_forecast_1h.csv": "",
        "solcast2022_global_actual.csv": "",
        "solcast2022_global_forecast_1h.csv": "",
    }
    _files = list(_checksums.keys())
    _hash_algorithm = "md5"

    def download(self) -> None:
        """Download Solcast data from url if not already downloaded."""
        if self.check_integrity(self._files, self._checksums, self._hash_algorithm):
            print("Files already downloaded and verified")
        else:
            urllib.request.urlretrieve(
                self._url, os.path.join(self._base_dir, self._file_name)
            )
            print(f"Data downloaded successfully to {self._base_dir}")

            self.unzip_file(self._file_name)

            if self.check_integrity(self._files, self._checksums, self._hash_algorithm):
                print("Successfully unpacked and verified data files")
            else:
                raise RuntimeError("Integrity of data could not be verified.")

    def get_solar_time_series_api(
        self, scenario: Literal["global", "germany"], solar_size: Union[int, float]
    ) -> TimeSeriesApi:
        return super().get_time_series_api(
            actual_file_name="solcast2022_{scenario}_actual.csv",
            actual_index_cols=[0, 1],
            actual_value_cols=["actual"],
            actual_transform=self._transform_solcast_data,
            fill_method="bfill",
            forecast_file_name="solcast2022_{scenario}_forecast_1h.csv",
            forecast_index_cols=[0, 1, 2],
            forecast_value_cols=["median"],
            forecast_transform=self._transform_solcast_data,
            solar_size=solar_size,
        )

    def _transform_solcast_data(self, df: pd.DataFrame, solar_size: Union[int, float]):
        return (df * solar_size).unstack(level=0)
