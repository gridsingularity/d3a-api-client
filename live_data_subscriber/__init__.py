import json
import logging
from os import environ
from time import time

from d3a_api_client.utils import list_running_canary_networks_and_devices_with_live_data, \
    get_area_uuid_and_name_mapping_from_simulation_id
from live_data_subscriber.constants import RELOAD_CN_DEVICE_LIST_TIMEOUT_SECONDS, \
    mqtt_devices_name_mapping, ws_devices_name_mapping


def generate_api_client_args_mapping(allowed_device_mapping):
    sim_api_domain_name = environ["API_CLIENT_SIM_API_DOMAIN_NAME"]
    external_api_domain_name = environ["API_CLIENT_DOMAIN_NAME"]
    websocket_api_domain_name = environ["API_CLIENT_WEBSOCKET_DOMAIN_NAME"]

    cn_mapping = list_running_canary_networks_and_devices_with_live_data(sim_api_domain_name)

    api_client_mapping = {v: [] for _, v in allowed_device_mapping.items()}

    logging.info(f"Canary Networks mapping {cn_mapping}")

    for configuration_id, live_data_device_mapping in cn_mapping.items():

        if not live_data_device_mapping:
            logging.info(f"No live data for CN {configuration_id}.")
            continue

        live_data_device_mapping = json.loads(live_data_device_mapping)

        api_client_args = {
            "simulation_id": configuration_id,
            "domain_name": external_api_domain_name,
            "sim_api_domain_name": sim_api_domain_name,
            "websockets_domain_name": websocket_api_domain_name,
            "autoregister": False,
            "start_websocket": False
        }

        live_data_device_uuids = live_data_device_mapping.keys()

        if not live_data_device_uuids:
            logging.info(f"No live data for CN {configuration_id}.")
            continue

        name_uuid_mapping = \
            get_area_uuid_and_name_mapping_from_simulation_id(configuration_id, sim_api_domain_name)
        # It is a prerequisite to have unique area names for this to work.
        uuid_name_mapping = {v: k for k, v in name_uuid_mapping.items()}
        for device_uuid in live_data_device_uuids:
            device_name = uuid_name_mapping[device_uuid]
            if device_name in allowed_device_mapping:
                api_client_mapping[allowed_device_mapping[device_name]].append(
                    {"device_id": device_uuid, **api_client_args}
                )
    return api_client_mapping


def refresh_cn_and_device_list(last_time_checked, api_client_dict, is_mqtt=False):
    if time() - last_time_checked >= RELOAD_CN_DEVICE_LIST_TIMEOUT_SECONDS:
        last_time_checked = time()
        allowed_device_mapping = mqtt_devices_name_mapping if is_mqtt else ws_devices_name_mapping
        api_client_dict = generate_api_client_args_mapping(allowed_device_mapping)
        log_text = f"MQTT topics" if is_mqtt else f"WS devices"
        logging.info(f"Connecting to the following {log_text} {api_client_dict}")
        return last_time_checked, api_client_dict
    return last_time_checked, api_client_dict
