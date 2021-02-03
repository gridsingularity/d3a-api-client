from enum import Enum


class Commands(Enum):
    OFFER = 1
    BID = 2
    DELETE_OFFER = 3
    DELETE_BID = 4
    LIST_OFFERS = 5
    LIST_BIDS = 6
    DEVICE_INFO = 7


command_enum_to_command_name_dict = {
    Commands.OFFER: "offer",
    Commands.BID: "bid",
    Commands.DELETE_OFFER: "delete_offer",
    Commands.DELETE_BID: "delete_bid",
    Commands.LIST_OFFERS: "list_offers",
    Commands.LIST_BIDS: "list_bids",
    Commands.DEVICE_INFO: "device_info"
}


def command_enum_to_command_name(command: Commands) -> str:
    return command_enum_to_command_name_dict[command]
