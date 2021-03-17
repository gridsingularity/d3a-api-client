import os
import json
import logging
import traceback
import paho.mqtt.client as mqtt
from time import time

from d3a_api_client.rest_device import RestDeviceClient
from live_data_subscriber import mqtt_devices_name_mapping, \
    refresh_cn_and_device_list
from live_data_subscriber.constants import RELOAD_CN_DEVICE_LIST_TIMEOUT_SECONDS, MQTT_PORT


class MQTTBrokerConnectionError(Exception):
    pass


class MQTTConnection:
    def __init__(self):
        self.last_time_checked, self.topic_api_client_dict = refresh_cn_and_device_list(
            last_time_checked=time() - RELOAD_CN_DEVICE_LIST_TIMEOUT_SECONDS,
            api_client_dict={v: [] for _, v in mqtt_devices_name_mapping.items()},
            is_mqtt=True
        )
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.run_forever()

    def on_connect(self, client, userdata, flags, rc):
        logging.info(f"Connected with result code {str(rc)}")

        for topic_name in mqtt_devices_name_mapping.values():
            logging.info(f"Subscribed to topic {topic_name}")
            subscribe_result = client.subscribe(topic_name)
            if subscribe_result[0] != 0:
                raise MQTTBrokerConnectionError(
                    f"Could not subscribe to topic {topic_name}. Subscribe error code {subscribe_result}."
                )

    def on_message(self, client, userdata, msg):
        logging.info(f"Received mqtt message {msg.topic} {str(msg.payload)}")
        try:
            self.last_time_checked, self.topic_api_client_dict = refresh_cn_and_device_list(
                self.last_time_checked, self.topic_api_client_dict, is_mqtt=True
            )
            payload = json.loads(msg.payload.decode("utf-8"))

            energy = payload["value"]

            # Transmit power values to CN
            for api_args in self.topic_api_client_dict[msg.topic]:
                RestDeviceClient(**api_args).set_energy_forecast(energy, do_not_wait=True)

        except Exception as e:
            logging.error(f"API Client failed to send energy forecasts to d3a with error {e}. "
                          f"Resuming operation.")
            logging.error(f"{traceback.format_exc()}")

    def run_forever(self):
        logging.info("Creating MQTT client")
        username = os.environ["MQTT_USERNAME"]
        password = os.environ["MQTT_PASSWORD"]
        domain_name = os.environ["MQTT_DOMAIN_NAME"]

        self.client.username_pw_set(username, password=password)
        self.client.connect(domain_name, MQTT_PORT)

        self.client.loop_forever()
