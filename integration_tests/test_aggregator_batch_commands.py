import logging

from d3a_api_client.redis_aggregator import RedisAggregator
from d3a_api_client.redis_device import RedisDeviceClient
from d3a_api_client.redis_market import RedisMarketClient


class BatchAggregator(RedisAggregator):
    def __init__(self, *args, **kwargs):
        self.grid_fees_market_cycle_next_market = {}
        self.grid_fees_tick_last_market = {}
        self.initial_grid_fees_market_cycle = {}
        super().__init__(*args, **kwargs)
        self.errors = 0
        self.status = "running"
        self._setup()
        self.is_active = True
        self.updated_house2_grid_fee_cents_kwh = 5

    def _setup(self):
        load = RedisDeviceClient('load', autoregister=True)
        pv = RedisDeviceClient('pv', autoregister=True)

        load.select_aggregator(self.aggregator_uuid)
        pv.select_aggregator(self.aggregator_uuid)

        self.redis_market = RedisMarketClient('house-2')
        self.redis_market.select_aggregator(self.aggregator_uuid)

    def require_grid_fees(self, grid_fee_buffer_dict, fee_type):
        load_uuid = self.get_uuid_from_area_name("load")
        for target_market in ["Grid", "House 1", "House 2"]:
            market_uuid = self.get_uuid_from_area_name(target_market)
            grid_fee_buffer_dict[target_market] = \
                self.calculate_grid_fee(load_uuid, market_uuid, fee_type)

    def on_market_cycle(self, market_info):
        logging.info(f"market_info: {market_info}")
        if self.initial_grid_fees_market_cycle == {}:
            self.require_grid_fees(self.initial_grid_fees_market_cycle, "last_market_fee")
        for area_uuid, area_dict in self.latest_grid_tree_flat.items():
            if "asset_info" not in area_dict or area_dict["asset_info"] is None:
                continue

            if "available_energy_kWh" in area_dict["asset_info"]  and \
                    area_dict["asset_info"]["available_energy_kWh"] > 0.0:
                self.add_to_batch_commands.offer_energy(area_uuid=area_uuid, price=1,
                                                        energy=area_dict["asset_info"]["available_energy_kWh"] / 2) \
                    .list_offers(area_uuid=area_uuid)

            if "energy_requirement_kWh" in area_dict["asset_info"] and \
                        area_dict["asset_info"]["energy_requirement_kWh"] > 0.0:
                    self.add_to_batch_commands.bid_energy(area_uuid=area_uuid, price=30,
                                                          energy=area_dict["asset_info"][
                                                                     "energy_requirement_kWh"] / 2) \
                        .list_bids(area_uuid=area_uuid)

            self.add_to_batch_commands.grid_fees(area_uuid=self.redis_market.area_uuid,
                                                 fee_cents_kwh=self.updated_house2_grid_fee_cents_kwh)
            self.add_to_batch_commands.last_market_dso_stats(self.redis_market.area_uuid)
            self.add_to_batch_commands.last_market_stats(self.redis_market.area_uuid)

        if self.commands_buffer_length:
            transaction = self.execute_batch_commands()
            if transaction is None:
                self.errors += 1
            else:
                for response in transaction["responses"]:
                    for area_response in response:
                        if area_response["status"] == "error":
                            self.errors += 1
            logging.info(f"Batch command placed on the new market")

        self.require_grid_fees(self.grid_fees_market_cycle_next_market, "current_market_fee")

    def on_tick(self, tick_info):
        self.require_grid_fees(self.grid_fees_tick_last_market, "last_market_fee")

    def on_finish(self, finish_info):
        self.status = "finished"
