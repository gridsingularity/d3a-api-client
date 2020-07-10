import logging
import json
import uuid
from enum import Enum
from functools import wraps
from redis import StrictRedis
from d3a_interface.utils import wait_until_timeout_blocking
from d3a_api_client import APIClientInterface
from concurrent.futures.thread import ThreadPoolExecutor
from d3a_api_client.constants import MAX_WORKER_THREADS

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)


class RedisAPIException(Exception):
    pass


def registered_connection(f):
    @wraps(f)
    def wrapped(self, *args, **kwargs):
        if not self.is_active:
            raise RedisAPIException(f'Registration has not completed yet.')
        return f(self, *args, **kwargs)
    return wrapped


class Commands(Enum):
    OFFER = 1
    BID = 2
    DELETE_OFFER = 3
    DELETE_BID = 4
    LIST_OFFERS = 5
    LIST_BIDS = 6
    DEVICE_INFO = 7


class RedisClient(APIClientInterface):
    def __init__(self, area_id, client_id, autoregister=True, redis_url='redis://localhost:6379',
                 is_before_launch=True, is_blocking=True):
        super().__init__(area_id, client_id, autoregister, redis_url)
        self.redis_db = StrictRedis.from_url(redis_url)
        self.pubsub = self.redis_db.pubsub()
        # TODO: Replace area_id (which is a area name slug now) with "area_uuid"
        self.area_id = area_id
        self.client_id = client_id
        self.device_uuid = None
        self.is_active = False
        self._blocking_command_responses = {}
        self._subscribe_to_response_channels()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)
        if autoregister:
            self.register(is_blocking=is_blocking, is_before_launch=is_before_launch)

    def _subscribe_to_response_channels(self):
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

        self.pubsub.subscribe(**channel_subs)
        self.pubsub.run_in_thread(daemon=True)

    def register(self, is_blocking=False, is_before_launch=False):
        logging.info(f"Trying to register to {self.area_id} as client {self.client_id}")
        if self.is_active:
            raise RedisAPIException(f'API is already registered to the market.')
        data = {"name": self.client_id, "transaction_id": str(uuid.uuid4())}
        if is_before_launch:
            self.redis_db.set(f'{self.area_id}/register_participant',
                              json.dumps({'data': json.dumps(data)}))
        else:
            self.redis_db.publish(f'{self.area_id}/register_participant', json.dumps(data))
        self._blocking_command_responses["register"] = data

        if is_blocking:
            try:
                wait_until_timeout_blocking(lambda: self.is_active, timeout=120)
            except AssertionError:
                raise RedisAPIException(
                    f'API registration process timed out. Server will continue processing your '
                    f'request on the background and will notify you as soon as the registration '
                    f'has been completed.')

    def unregister(self, is_blocking=False):

        logging.info(f"Trying to unregister from {self.area_id} as client {self.client_id}")

        if not self.is_active:
            raise RedisAPIException(f'API is already unregistered from the market.')

        data = {"name": self.client_id, "transaction_id": str(uuid.uuid4())}
        self.redis_db.publish(f'{self.area_id}/unregister_participant', json.dumps(data))
        self._blocking_command_responses["unregister"] = data

        if is_blocking:
            try:
                wait_until_timeout_blocking(lambda: not self.is_active, timeout=120)
            except AssertionError:
                raise RedisAPIException(
                    f'API unregister process timed out. Server will continue processing your '
                    f'request on the background and will notify you as soon as the unregistration '
                    f'has been completed.')

    @property
    def _channel_prefix(self):
        return f"{self.area_id}/{self.client_id}"

    @property
    def _command_topics(self):
        return {
            Commands.OFFER: f'{self._channel_prefix}/offer',
            Commands.BID: f'{self._channel_prefix}/bid',
            Commands.DELETE_OFFER: f'{self._channel_prefix}/delete_offer',
            Commands.DELETE_BID: f'{self._channel_prefix}/delete_bid',
            Commands.LIST_OFFERS: f'{self._channel_prefix}/list_offers',
            Commands.LIST_BIDS: f'{self._channel_prefix}/list_bids',
            Commands.DEVICE_INFO: f'{self._channel_prefix}/device_info'
        }

    @property
    def _response_topics(self):
        response_prefix = self._channel_prefix + "/response"
        return {
            Commands.OFFER: f'{response_prefix}/offer',
            Commands.BID: f'{response_prefix}/bid',
            Commands.DELETE_OFFER: f'{response_prefix}/delete_offer',
            Commands.DELETE_BID: f'{response_prefix}/delete_bid',
            Commands.LIST_OFFERS: f'{response_prefix}/list_offers',
            Commands.LIST_BIDS: f'{response_prefix}/list_bids',
            Commands.DEVICE_INFO: f'{response_prefix}/device_info',
        }

    def _wait_and_consume_command_response(self, command_type, transaction_id):
        def check_if_command_response_received():
            return any(command == command_type and
                       "transaction_id" in data and data["transaction_id"] == transaction_id
                       for command, data in self._blocking_command_responses.items())
        logging.debug(f"Command {command_type} waiting for response...")
        wait_until_timeout_blocking(check_if_command_response_received, timeout=120)
        command_output = self._blocking_command_responses.pop(command_type)
        logging.debug(f"Command {command_type} got response {command_output}")
        return command_output

    def _generate_command_response_callback(self, command_type):
        def _command_received(msg):
            try:
                message = json.loads(msg["data"])
            except Exception as e:
                logging.error(f"Received incorrect response on command {command_type}. "
                              f"Response {msg}. Error {e}.")
                return
            logging.debug(f"Command {command_type} received response: {message}")
            if 'error' in message:
                logging.error(f"Error when receiving {command_type} command response."
                              f"Error output: {message}")
                return
            else:
                self._blocking_command_responses[command_type] = message
        return _command_received

    def _publish_and_wait(self, command_type, data):
        data.update({"transaction_id": str(uuid.uuid4())})
        self.redis_db.publish(self._command_topics[command_type], json.dumps(data))
        return self._wait_and_consume_command_response(command_type, data["transaction_id"])

    @registered_connection
    def offer_energy(self, energy, price):
        logging.debug(f"Client tries to place an offer for {energy} kWh at {price} cents.")
        return self._publish_and_wait(Commands.OFFER, {"energy": energy, "price": price})

    @registered_connection
    def offer_energy_rate(self, energy, rate):
        logging.debug(f"Client tries to place an offer for {energy} kWh at {rate} cents/kWh.")
        return self._publish_and_wait(Commands.OFFER, {"energy": energy, "price": rate * energy})

    @registered_connection
    def bid_energy(self, energy, price):
        logging.debug(f"Client tries to place a bid for {energy} kWh at {price} cents.")
        return self._publish_and_wait(Commands.BID, {"energy": energy, "price": price})

    @registered_connection
    def bid_energy_rate(self, energy, rate):
        logging.debug(f"Client tries to place a bid for {energy} kWh at {rate} cents/kWh.")
        return self._publish_and_wait(Commands.BID, {"energy": energy, "price": rate * energy})

    @registered_connection
    def delete_offer(self, offer_id=None):
        if offer_id is None:
            logging.debug(f"Client tries to delete all offers.")
        else:
            logging.debug(f"Client tries to delete offer {offer_id}.")
        return self._publish_and_wait(Commands.DELETE_OFFER, {"offer": offer_id})

    @registered_connection
    def delete_bid(self, bid_id=None):
        if bid_id is None:
            logging.debug(f"Client tries to delete all bids.")
        else:
            logging.debug(f"Client tries to delete bid {bid_id}.")
        return self._publish_and_wait(Commands.DELETE_BID, {"bid": bid_id})

    @registered_connection
    def list_offers(self):
        logging.debug(f"Client tries to read its posted offers.")
        return self._publish_and_wait(Commands.LIST_OFFERS, {})

    @registered_connection
    def list_bids(self):
        logging.debug(f"Client tries to read its posted bids.")
        return self._publish_and_wait(Commands.LIST_BIDS, {})

    @registered_connection
    def device_info(self):
        logging.debug(f"Client tries to read the device information.")
        return self._publish_and_wait(Commands.DEVICE_INFO, {})

    def _on_register(self, msg):
        message = json.loads(msg["data"])
        self._check_buffer_message_matching_command_and_id(message)
        if 'available_publish_channels' not in message or \
                'available_subscribe_channels' not in message:
            raise RedisAPIException(f'Registration to the market {self.area_id} failed.')

        logging.info(f"Client was registered to market: {message}")
        self.is_active = True

        def executor_function():
            self.on_register(message)
        self.executor.submit(executor_function)

    def _on_unregister(self, msg):
        message = json.loads(msg["data"])
        self._check_buffer_message_matching_command_and_id(message)
        self.is_active = False
        if message["response"] != "success":
            raise RedisAPIException(f'Failed to unregister from market {self.area_id}.'
                                    f'Deactivating connection.')

    def _on_market_cycle(self, msg):
        message = json.loads(msg["data"])
        logging.debug(f"A new market was created. Market information: {message}")

        def executor_function():
            self.on_market_cycle(message)
        self.executor.submit(executor_function)

    def _on_tick(self, msg):
        message = json.loads(msg["data"])
        logging.debug(f"Time has elapsed on the device. Progress info: {message}")

        def executor_function():
            self.on_tick(message)
        self.executor.submit(executor_function)

    def _on_trade(self, msg):
        message = json.loads(msg["data"])
        logging.debug(f"A trade took place on the device. Trade information: {message}")

        def executor_function():
            self.on_trade(message)
        self.executor.submit(executor_function)

    def _on_finish(self, msg):
        message = json.loads(msg["data"])
        logging.info(f"Simulation finished. Information: {message}")

        def executor_function():
            self.on_finish(message)
        self.executor.submit(executor_function)

    def _check_buffer_message_matching_command_and_id(self, message):
        if "transaction_id" in message and message["transaction_id"] is not None:
            transaction_id = message["transaction_id"]
            if not any(command in ["register", "unregister"] and "transaction_id" in data and
                       data["transaction_id"] == transaction_id
                       for command, data in self._blocking_command_responses.items()):
                raise RedisAPIException("There is no matching command response in _blocking_command_responses.")
        else:
            raise RedisAPIException(
                "the answer message does not contain a valid 'transaction_id' member.")

    def on_register(self, registration_info):
        pass

    def on_market_cycle(self, market_info):
        pass

    def on_tick(self, tick_info):
        pass

    def on_trade(self, trade_info):
        pass

    def on_finish(self, finish_info):
        pass