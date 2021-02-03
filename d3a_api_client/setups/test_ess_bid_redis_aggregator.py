import logging
from time import sleep
from d3a_api_client.redis_aggregator import RedisAggregator
from d3a_api_client.redis_device import RedisDeviceClient


class AutoAggregator(RedisAggregator):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_finished = False

    def on_market_cycle(self, market_info):
        logging.info(f"market_info: {market_info}")
        batch_commands = {}

        for device_event in market_info["content"]:
            logging.info(f"device_event: {device_event}")
            if "energy_to_buy" in device_event["device_info"] and \
                    device_event["device_info"]["energy_to_buy"] > 0.0:
                buy_energy = device_event["device_info"]["energy_to_buy"] / 2
                batch_commands[device_event["area_uuid"]] = [
                    {"type": "bid",
                     "price": 31 * buy_energy,
                     "energy": buy_energy},
                    {"type": "list_bids"}]

        logging.info(f"batch_commands: {batch_commands}")

        if batch_commands:
            self.batch_command(batch_commands)
            logging.info(f"Batch command placed on the new market")

    def on_tick(self, tick_info):
        logging.info(f"AGGREGATOR_TICK_INFO: {tick_info}")

    def on_trade(self, trade_info):
        logging.info(f"AGGREGATOR_TRADE_INFO: {trade_info}")

    def on_finish(self, finish_info):
        self.is_finished = True
        logging.info(f"AGGREGATOR_FINISH_INFO: {finish_info}")


aggregator = AutoAggregator(
    aggregator_name="faizan_aggregator",
    autoregister=True)

sleep(10)
# aggregator.delete_aggregator(is_blocking=True)


# Connects one client to the storage device
storage = RedisDeviceClient('storage', autoregister=True)

sleep(5)
selected = storage.select_aggregator(aggregator.aggregator_uuid)
logging.info(f"SELECTED: {selected}")

while not aggregator.is_finished:
    sleep(0.5)
