import logging
import traceback
from live_data.mqtt_subscriber import generate_api_client_args_mapping
from live_data.mqtt_subscriber.oli_broker import MQTTConnection
from multiprocessing import Process
from live_data.websocket_subscriber import create_live_data_consumer


def main():
    logging.getLogger().setLevel(logging.INFO)
    topic_api_client_mapping, device_api_client_mapping = generate_api_client_args_mapping()

    # Connect to the MQTT broker
    try:
        p1 = Process(target=create_live_data_consumer(device_api_client_mapping))
        p1.start()
    except Exception as e:
        logging.error(f"WS Subscriber failed with error {e}")
        logging.error(traceback.format_exc())

    try:
        p2 = Process(target=MQTTConnection(topic_api_client_mapping).run_forever())
        p2.start()
    except Exception as e:
        logging.error(f"MQTT Subscriber failed with error {e}")
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    main()