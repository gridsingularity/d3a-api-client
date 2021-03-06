from behave import given, when, then
from os import system
from time import sleep
from math import isclose

from integration_tests.test_aggregator_batch_commands import BatchAggregator
from integration_tests.test_load_connection import AutoBidOnLoadDevice
from integration_tests.test_pv_connection import AutoOfferOnPVDevice
from integration_tests.test_ess_bid_connection import AutoBidOnESSDevice
from integration_tests.test_ess_offer_connection import AutoOfferOnESSDevice


@given('redis container is started')
def step_impl(context):
    system(f'docker run -d -p 6379:6379 --name redis.container -h redis.container '
           '--net integtestnet gsyd3a/d3a:redis-staging')


@given('d3a is started using setup {setup_file} ({d3a_options})')
def step_impl(context, setup_file: str, d3a_options: str):
    """Run the d3a container on a specific setup.

    Args:
        setup_file (str): the setup file for a d3a simulation.
        d3a_options (str): options to be passed to the d3a run command. E.g.: "-t 1s -d 12h"
    """
    sleep(3)
    system(f'docker run -d --name d3a-tests --env REDIS_URL=redis://redis.container:6379/ '
           f'--net integtestnet d3a-tests -l INFO run --setup {setup_file} '
           f'--no-export --seed 0 --enable-external-connection {d3a_options}')


@when('the external client is started with test_load_connection')
def step_impl(context):
    # Wait for d3a to activate all areas
    sleep(5)
    # Connects one client to the load device
    context.device = AutoBidOnLoadDevice('load', autoregister=True,
                                         redis_url='redis://localhost:6379/')
    sleep(3)
    assert context.device.is_active is True


@when('the external client is started with test_aggregator_batch_commands')
def step_impl(context):
    # Wait for d3a to activate all areas
    sleep(5)
    # Connects one client to the load device
    context.device = BatchAggregator(aggregator_name="My_aggregator")
    sleep(3)
    assert context.device.is_active is True


@when('the external client is started with test_pv_connection')
def step_impl(context):
    # Wait for d3a to activate all areas
    sleep(5)
    # Connects one client to the load device
    context.device = AutoOfferOnPVDevice('pv', autoregister=True,
                                         redis_url='redis://localhost:6379/')


@then('the on_event_or_response is called for different events')
def step_impl(context):
    # Check if the market event triggered both the on_market_cycle and on_event_or_response
    assert context.device.events == {'event', 'command',
                                     'tick', 'register',
                                     'offer_delete', 'trade',
                                     'offer', 'unregister',
                                     'list_offers', 'market', 'finish'}
    assert context.device.is_on_market_cycle_called


@when('the external client is started with test_ess_bid_connection')
def step_impl(context):
    # Wait for d3a to activate all areas
    sleep(5)
    # Connects one client to the load device
    context.device = AutoBidOnESSDevice('storage', autoregister=True,
                                        redis_url='redis://localhost:6379/')


@when('the external client is started with test_ess_offer_connection')
def step_impl(context):
    # Wait for d3a to activate all areas
    sleep(5)
    # Connects one client to the load device
    context.device = AutoOfferOnESSDevice('storage', autoregister=True,
                                          redis_url='redis://localhost:6379/')


@then('the external client is connecting to the simulation until finished')
def step_impl(context):
    # Infinite loop in order to leave the client running on the background
    # placing bids and offers on every market cycle.
    # Should stop if an error occurs or if the simulation has finished
    counter = 0  # Wait for five minutes at most
    while context.device.errors == 0 and context.device.status != "finished" and counter < 900:
        sleep(3)
        counter += 3


@then('the external client does not report errors')
def step_impl(context):
    assert context.device.errors == 0


@then('the storage is not overcharged')
def step_impl(context):
    assert context.device.last_market_info["device_info"]["used_storage"] <= 20.0


@then('the storage state is limited to min_allowed_soc')
def step_impl(context):
    assert context.device.last_market_info["device_info"]["used_storage"] >= 2.0


@then('the energy bills of the load report the required energy was bought by the load')
def step_impl(context):
    assert isclose(context.device.device_bills["bought"], 22 * 0.2)

