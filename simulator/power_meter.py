from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Tuple, Dict

import boto3


class PowerModel:
    def __init__(self, p_static, p_max):
        self.p_static = p_static
        self.p_max = p_max

    def __call__(self, utilization):
        return self.p_static + utilization * (self.p_max - self.p_static)


class PowerMeter(ABC):

    def power_usage(self) -> Tuple[float, Dict[str, float]]:
        return self.node_power_usage(), self.application_power_usage()

    @abstractmethod
    def node_power_usage(self):
        pass

    def application_power_usage(self) -> Dict[str, float]:
        # TODO Explain
        # TODO measure resource utilization of containers/cgroups/processes
        # in a first version we only care for CPU
        return {
            "process1": 1.98,
            "process2": 0.23
        }


class VirtualPowerMeter(PowerMeter, ABC):
    def __init__(self, power_model: PowerModel):
        self.power_model = power_model

    def node_power_usage(self):
        return self.power_model(self.utilization())

    @abstractmethod
    def utilization(self) -> float:
        pass


class AwsPowerMeter(VirtualPowerMeter):
    def __init__(self, instance_id: str, power_model: PowerModel):
        super().__init__(power_model)
        self.instance_id = instance_id

    def utilization(self) -> float:
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


class PhysicalPowerMeter(PowerMeter):

    def node_power_usage(self):
        # TODO measure device power usage
        return 10
