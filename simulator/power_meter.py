from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Tuple, Dict, Callable, Optional
import paho.mqtt.client as mqtt


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


class PhysicalPowerMeter(PowerMeter):
    def __init__(self, host: str = "localhost", port: int = 1883, keepalive: int = 60, name: Optional[str] = None):
        """
        Initializes a new instance of the PhysicalPowerMeter class, an MQTT
        wrapper that serves as an adapter for physical nodes (HIL) to submit
        their power usage.

        :param host: The hostname or IP address of the MQTT broker. Default is "localhost".
        :param port: The port number to use for the MQTT connection. Default is 1883.
        :param keepalive: The maximum period in seconds allowed between communications with the MQTT broker. Default is 60.
        """

        super().__init__(name)
        # create MQTT client instance
        self.client = mqtt.Client()
        # assign the on_connect and on_message methods to the MQTT client's corresponding attributes
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        # connect the MQTT client to the broker with the provided host, port, and keepalive values
        self.client.connect(host, port=port, keepalive=keepalive)
        # the last received power value from client
        self.last_node_power = 0

    # on_connect method that gets called when the MQTT client connects to the broker
    def on_connect(self, client, userdata, flags, rc):
        print(f"PhysicalPowerMeter: Connected with result code {str(rc)}")
        # subscribe to the "node_power" topic
        self.client.subscribe("node_power")

    # on_message method that gets called when a message is received on the subscribed topic
    def on_message(self, client, userdata, msg):
        # decode the message payload and store it as float in last_node_power
        self.last_node_power = float(msg.payload.decode())

    # node_power method to retrieve the last received power value
    def node_power(self) -> float:
        return self.last_node_power


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
