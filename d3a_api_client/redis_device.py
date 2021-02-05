import logging
import json
import uuid

from d3a_api_client.redis_client_base import RedisClient, Commands
from d3a_interface.utils import wait_until_timeout_blocking
from d3a_api_client.utils import RedisAPIException


class RedisDeviceClient(RedisClient):
    def __init__(self, device_id, autoregister=True, redis_url='redis://localhost:6379',
                 pubsub_thread=None):

        self.device_id = device_id
        self._transaction_id_buffer = []
        super().__init__(device_id, None, autoregister, redis_url, pubsub_thread)

    def _on_register(self, msg):
        message = json.loads(msg["data"])
        self.device_uuid = message['device_uuid']
        self._check_buffer_message_matching_command_and_id(message)
        logging.info(f"Client was registered to the device: {message}")
        self.is_active = True
        self.device_uuid = message['device_uuid']

    def _on_unregister(self, msg):
        message = json.loads(msg["data"])
        self._check_buffer_message_matching_command_and_id(message)
        logging.info(f"Client was unregistered from the device: {message}")
        self.is_active = False

    def _subscribe_to_response_channels(self, pubsub_thread=None):
        channel_subs = {
            self._response_topics[c]: self._generate_command_response_callback(c)
            for c in Commands
        }

        channel_subs[f'{self.area_id}/response/register_participant'] = self._on_register
        channel_subs[f'{self.area_id}/response/unregister_participant'] = self._on_unregister
        channel_subs[f'{self._channel_prefix}/events/market'] = self._on_market_cycle
        channel_subs[f'{self._channel_prefix}/events/tick'] = self._on_tick
        channel_subs[f'{self._channel_prefix}/events/trade'] = self._on_trade
        channel_subs[f'{self._channel_prefix}/events/finish'] = self._on_finish
        channel_subs["aggregator_response"] = self._aggregator_response_callback
        channel_subs[f'{self._channel_prefix}/*'] = self._on_event_or_response
        self.pubsub.psubscribe(**channel_subs)
        if pubsub_thread is None:
            self.redis_thread = self.pubsub.run_in_thread(daemon=True)

    def _aggregator_response_callback(self, message):
        data = json.loads(message['data'])
        if data['transaction_id'] in self._transaction_id_buffer:
            self._transaction_id_buffer.pop(self._transaction_id_buffer.index(data['transaction_id']))

    def _check_transaction_id_cached_out(self, transaction_id):
        return transaction_id in self._transaction_id_buffer

    def select_aggregator(self, aggregator_uuid, is_blocking=True, unsubscribe_from_device_events=True):
        logging.info(f"Device: {self.device_id} is trying to select aggregator {aggregator_uuid}")

        transaction_id = str(uuid.uuid4())
        data = {"aggregator_uuid": aggregator_uuid,
                "device_uuid": self.device_uuid,
                "type": "SELECT",
                "transaction_id": transaction_id}
        self.redis_db.publish(f'aggregator', json.dumps(data))
        self._transaction_id_buffer.append(transaction_id)

        if is_blocking:
            try:
                wait_until_timeout_blocking(
                    lambda: self._check_transaction_id_cached_out(transaction_id)
                )
                logging.info(f"DEVICE: {self.device_uuid} has selected "
                             f"AGGREGATOR: {aggregator_uuid}")
                return transaction_id
            except AssertionError:
                raise RedisAPIException(f'API has timed out.')
        if unsubscribe_from_device_events:
            self.pubsub.unsubscribe(
                [f'{self.area_id}/response/register_participant',
                 f'{self.area_id}/response/unregister_participant',
                 f'{self._channel_prefix}/events/market',
                 f'{self._channel_prefix}/events/tick',
                 f'{self._channel_prefix}/events/trade',
                 f'{self._channel_prefix}/events/finish']
            )

    def unselect_aggregator(self, aggregator_uuid):
        raise NotImplementedError("unselect_aggregator hasn't been implemented yet.")

    @property
    def _channel_prefix(self):
        return f"{self.device_id}"
