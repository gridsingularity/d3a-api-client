"""
Test file for the device client. Depends on d3a test setup file strategy_tests.external_devices
"""
import logging
import json
import traceback
from d3a_api_client.types import device_client_type


class AutoBidOnLoadDevice(device_client_type):
    def __init__(self, *args, **kwargs):
        self.errors = 0
        self.error_list = []
        self.status = "running"
        self.latest_stats = {}
        self.market_info = {}
        self.device_bills = {}
        super().__init__(*args, **kwargs)

    def on_market_cycle(self, market_info):
        try:
            assert "energy_requirement_kWh" in market_info["device_info"]
            energy_requirement = market_info["device_info"]["energy_requirement_kWh"]
            if energy_requirement > 0.001:
                # Placing a cheap bid to the market that will not be accepted
                bid = self.bid_energy(energy_requirement, 0.0001 * energy_requirement)
                bid_info = json.loads(bid["bid"])
                assert bid_info["price"] == 0.0001 * energy_requirement
                assert bid_info["energy"] == energy_requirement
                # Validate that the bid was placed to the market
                bid_listing = self.list_bids()
                listed_bid = next(bid for bid in bid_listing["bid_list"] if bid["id"] == bid_info["id"])
                assert listed_bid["price"] == bid_info["price"]
                assert listed_bid["energy"] == bid_info["energy"]
                # Try to delete the bid
                delete_resp = self.delete_bid(bid_info["id"])
                assert delete_resp["deleted_bids"] == [bid_info["id"]]
                # Validate that the bid was deleted from the market
                empty_listing = self.list_bids()
                assert not any(b for b in empty_listing["bid_list"] if b["id"] == bid_info["id"])
                # Place the bid with a rate that will be acceptable for trading
                bid = self.bid_energy_rate(energy_requirement, 33)
                bid_info = json.loads(bid["bid"])
                assert bid_info["price"] == 33 * energy_requirement
                assert bid_info["energy"] == energy_requirement

            assert "device_bill" in market_info
            self.device_bills = market_info["device_bill"]
            assert set(self.device_bills.keys()) == \
                   {'earned', 'bought', 'total_energy', 'total_cost', 'market_fee', 'type', 'spent', 'sold'}
            assert "last_market_stats" in market_info
            assert set(market_info["last_market_stats"]) == \
                   {'min_trade_rate', 'max_trade_rate', 'avg_trade_rate', 'median_trade_rate',
                    'total_traded_energy_kWh'}

            if market_info["start_time"][-5:] == "23:00":
                self.status = "finished"
                self.unregister()

            self.market_info = market_info

        except AssertionError as e:
            logging.error(f"Raised exception: {e}. Traceback: {traceback.format_exc()}")
            self.errors += 1
            self.error_list.append(e)
            raise e
