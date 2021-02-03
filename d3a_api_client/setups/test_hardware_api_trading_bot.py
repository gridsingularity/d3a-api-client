"""
Test file for the device client. Depends on d3a test setup file strategy_tests.external_devices
"""
import os
import logging
from time import sleep
from d3a_api_client.rest_device import RestDeviceClient
from d3a_api_client.utils import get_area_uuid_from_area_name_and_collaboration_id


class AutoOfferBidHardwareApi(RestDeviceClient):

    def on_market_cycle(self, market_info):
        """
        Places a bid or an offer whenever a new market is created. The amount of energy
        for the bid/offer depends on the available energy of the PV, or on the required
        energy of the load.
        :param market_info: Incoming message containing the newly-created market info
        :return: None
        """
        logging.debug(f"New market information {market_info}")
        if "energy_requirement_kWh" in market_info["device_info"] and market_info["device_info"]["energy_requirement_kWh"] > 0.0:
            energy_forecast = market_info["device_info"]["energy_requirement_kWh"]
            bid = self.bid_energy_rate(energy_forecast / 2, 3)
            logging.info(f"Bid placed on the new market: {bid}")

        if "available_energy_kWh" in market_info["device_info"] and market_info["device_info"]["available_energy_kWh"] > 0.0:
            energy_forecast = market_info["device_info"]["available_energy_kWh"]
            offer = self.offer_energy_rate(energy_forecast/2, 1)
            logging.info(f"Offer placed on the new market: {offer}")

    def on_tick(self, tick_info):
        logging.debug(f"Progress information on the device: {tick_info}")

    def on_trade(self, trade_info):
        logging.debug(f"Trade info: {trade_info}")


os.environ["API_CLIENT_USERNAME"] = ""
os.environ["API_CLIENT_PASSWORD"] = ""
simulation_id = "4de1f0b4-f2bc-4c78-8cb9-a9941cab3a46"
domain_name = "http://localhost:8000"
websocket_domain_name = 'ws://localhost:8000/external-ws'

device_args = {
    "simulation_id": simulation_id,
    "domain_name": domain_name,
    "websockets_domain_name": websocket_domain_name,
    "autoregister": True
}

load_uuid = get_area_uuid_from_area_name_and_collaboration_id(
    device_args["simulation_id"], "load", device_args["domain_name"])
device_args["device_id"] = load_uuid
load = AutoOfferBidHardwareApi(
    **device_args)

pv_uuid = get_area_uuid_from_area_name_and_collaboration_id(
    device_args["simulation_id"], "pv", device_args["domain_name"])
device_args["device_id"] = pv_uuid
pv = AutoOfferBidHardwareApi(
    **device_args)


while True:
    sleep(0.5)
