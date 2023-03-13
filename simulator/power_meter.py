from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Tuple, Dict, Callable, Optional
from ina219 import INA219

PowerModel = Callable[[float], float]
POWER_METER_COUNT = 0


class LinearPowerModel:
    def __init__(self, p_static, p_max):
        self.p_static = p_static
        self.p_max = p_max

    def __call__(self, utilization: float) -> float:
        return self.p_static + utilization * (self.p_max - self.p_static)


class PowerMeter(ABC):
    def __init__(self, name: Optional[str] = None):
        global POWER_METER_COUNT
        POWER_METER_COUNT += 1
        if name is None:
            self.name = f"power_meter_{POWER_METER_COUNT}"
        else:
            self.name = name

    @abstractmethod
    def node_power(self) -> float:
        """Measures and returns the current node power demand."""


"""
Physical power meter for a raspberry pi with an INA219 for power measurement.
"""
class PhysicalPowerMeter(PowerMeter):
    def __init__(self, address=0x45) -> None:
        self.ina = INA219(0.1, address=address)
        self.ina.configure()

    def node_power(self):
        return round(self.ina.power() / 1000, 2)


class VirtualPowerMeter(PowerMeter, ABC):
    def __init__(self, power_model: PowerModel, name: Optional[str] = None):
        super().__init__(name)
        self.power_model = power_model

    def node_power(self):
        return self.power_model(self.utilization())

    @abstractmethod
    def utilization(self) -> float:
        """Measures and returns the current utilization [0,1] which is the input to the power model."""


class AwsPowerMeter(VirtualPowerMeter):
    def __init__(self, instance_id: str, power_model: PowerModel, name: Optional[str] = None):
        super().__init__(power_model, name)
        self.instance_id = instance_id

    def utilization(self) -> float:
        return 0.8

        import boto3
        client = boto3.client('cloudwatch')
        response = client.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[
                {
                    'Name': 'InstanceId',
                    'Value': self.instance_id
                },
            ],
            StartTime=datetime(2018, 4, 23) - timedelta(seconds=600),
            EndTime=datetime(2018, 4, 24),
            Period=86400,
            Statistics=[
                'Average',
            ],
            Unit='Percent'
        )

        for cpu in response['Datapoints']:
            if 'Average' in cpu:
                print(cpu['Average'])
