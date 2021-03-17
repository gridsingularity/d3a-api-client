MEASUREMENT_PERIOD_MINUTES = 15
RELOAD_CN_DEVICE_LIST_TIMEOUT_SECONDS = 60 * MEASUREMENT_PERIOD_MINUTES
MINUTES_IN_HOUR = 60
MQTT_PORT = 1883

mqtt_devices_name_mapping = {
    "OLI_42": "DOSE/OLI_42/Meter/activeEnergy/Demand",
    "OLI_6": "DOSE/OLI_6/PV/activeEnergy/Supply",
    "OLI_7": "DOSE/OLI_7/PV/activeEnergy/Supply",
    "OLI_8": "DOSE/OLI_8/Meter/activeEnergy/Demand",
    "OLI_9": "DOSE/OLI_9/Meter/activeEnergy/Demand",
    "OLI_28": "DOSE/OLI_28/PV/activeEnergy/Supply",
    "OLI_77": "DOSE/OLI_77/Meter/activeEnergy/Demand",
    "OLI_62": "WIRCON/OLI_62/PV/activeEnergy/Supply",
    "OLI_61": "WIRCON/OLI_61/PV/activeEnergy/Supply",
    "OLI_26": "WIRCON/OLI_26/PV/activeEnergy/Supply",
    "OLI_24": "WIRCON/OLI_24/PV/activeEnergy/Supply",
    "OLI_23": "WIRCON/OLI_23/PV/activeEnergy/Supply",
    "OLI_IDS_3": "EXA/OLI_IDS_3/WPP/activeEnergy/Supply"
}
ws_devices_name_mapping = {
    "OLI_42": "OLI_42",
    "OLI_6": "OLI_6",
    "OLI_7": "OLI_7",
    "OLI_8": "OLI_8",
    "OLI_9": "OLI_9",
    "OLI_28": "OLI_28",
    "OLI_77": "OLI_77",
    "OLI_62": "OLI_62",
    "OLI_61": "OLI_61",
    "OLI_26": "OLI_26",
    "OLI_24": "OLI_24",
    "OLI_23": "OLI_23",
    "OLI_IDS_3": "OLI_IDS_3"
}