import pandas as pd

from typing import Optional, Callable, Literal, List, Union
from vessim import TimeSeriesApi

class DataLoader:
    def __init__(self, base_dir: str, download: bool = False):
        self._base_dir = base_dir

    def get_time_series_api(
        self,
        actual_file_name: str,
        actual_index_col: str,
        actual_value_cols: Optional[List[str]] = None,
        actual_transform: Optional[Callable] = None,
        forecast_file_name: Optional[str] = None,
        forecast_index_cols: Optional[List[str]] = None,
        forecast_value_cols: Optional[List[str]] = None,
        forecast_transform: Optional[Callable] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
        *args,
        **kwargs,
    ) -> TimeSeriesApi:
        actual = self._read_data_from_csv(
            actual_file_name,
            actual_index_col,
            actual_value_cols,
            actual_transform,
            *args,
            **kwargs,
        )
        forecast: Optional[Union[pd.Series, pd.DataFrame]] = None
        if forecast_file_name is not None:
            forecast = self._read_data_from_csv(
                forecast_file_name,
                forecast_index_cols,
                forecast_value_cols,
                forecast_transform,
                *args,
                **kwargs,
            )
        return TimeSeriesApi(actual, forecast, fill_method)

    def _read_data_from_csv(
        self,
        file_name: str,
        index_cols: Optional[Union[str, List[str]]],
        value_cols: Optional[List[str]],
        transform: Optional[Callable],
        *args,
        **kwargs,
    ) -> Union[pd.Series, pd.DataFrame]:
        data = pd.read_csv(
            f"{self._base_dir}/{file_name}", index_col=index_cols, parse_dates=True
        )
        if value_cols is not None:
            data = data[value_cols]
        if transform is not None:
            data = transform(data, *args, **kwargs)
        return data.astype(float)
