import logging
from d3a_api_client.rest_device import logging_decorator
from concurrent.futures.thread import ThreadPoolExecutor
from d3a_api_client.websocket_device import WebsocketMessageReceiver, WebsocketThread
from d3a_api_client.utils import retrieve_jwt_key_from_server, RestCommunicationMixin
from d3a_api_client.constants import MAX_WORKER_THREADS


root_logger = logging.getLogger()
root_logger.setLevel(logging.ERROR)


class RestMarketClient(RestCommunicationMixin):

    def __init__(self, simulation_id, device_id, domain_name,
                 websockets_domain_name):
        self.simulation_id = simulation_id
        self.device_id = device_id
        self.domain_name = domain_name
        self.jwt_token = retrieve_jwt_key_from_server(domain_name)

        self.dispatcher = WebsocketMessageReceiver(self)
        self.websocket_thread = WebsocketThread(simulation_id, device_id, self.jwt_token,
                                                websockets_domain_name, self.dispatcher)
        self.websocket_thread.start()
        self.callback_thread = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)

    @property
    def _url_prefix(self):
        return f'{self.domain_name}/external-connection/api/{self.simulation_id}/{self.device_id}'

    @logging_decorator('market_stats')
    def list_market_stats(self, selected_markets):
        transaction_id, posted = self._get_request('market-stats', {"market_slots": selected_markets})
        if posted:
            return self.dispatcher.wait_for_command_response('market_stats', transaction_id)

    @logging_decorator('grid_fees')
    def grid_fees(self, fee_cents_per_kWh):
        transaction_id, get_sent = self._post_request('grid-fees', {"fee": fee_cents_per_kWh})
        if get_sent:
            return self.dispatcher.wait_for_command_response('grid_fees', transaction_id)
