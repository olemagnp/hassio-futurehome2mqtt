import time

import paho.mqtt.client as client
import pyfimptoha.sensor as sensor
import pyfimptoha.meter_elec as meter_elec
import pyfimptoha.light as light
import pyfimptoha.lock as lock
import pyfimptoha.appliance as appliance
import pyfimptoha.thermostat as thermostat
import pyfimptoha.shortcut as shortcut_button
import pyfimptoha.mode as mode_select


SUPPORTED_SENSORS = ["battery", "sensor_lumin", "sensor_presence", "sensor_temp", "sensor_humid"]
SUPPORTED_LIGHTS = ["out_lvl_switch", "out_bin_switch"]


def create_components(
        devices: list,
        rooms: list,
        shortcuts: list,
        mode: str,
        selected_devices: list,
        mqtt: client,
):
    """
    Creates HA components out of FIMP devices
    by pushing them to Home Assistant using MQTT discovery
    """

    print('Received list of devices from FIMP. FIMP reported %s devices' % (len(devices)))
    print('Devices without rooms will be ignored')

    statuses = []

    for device in devices:
        # Skip device without room
        room_id = device["room"]
        if room_id is None:
            continue

        address = device["fimp"]["address"]
        adapter = get_adapter_name(device)
        name = device["client"]["name"]
        vinc_id = device["id"]
        functionality = device["functionality"]
        room_alias = get_room_alias(rooms, room_id)

        # When debugging: Ignore everything except selected_devices if set
        # Format is '<adapter>_<address>', to not have conflicting addresses on different adapters
        if selected_devices and f"{adapter}_{address}" not in selected_devices:
            print(f"Skipping: {adapter} {address} {name}")
            continue

        print(f"Creating: {adapter} {address} {name}")
        print(f"- Functionality: {functionality}")

        for service_name, service in device["services"].items():
            status = None

            # Reusable
            identifier = f"fh_{vinc_id}_{adapter}_{address}_{service_name}"
            state_topic = f"pt:j1/mt:evt{service['addr']}"
            command_topic = f"pt:j1/mt:cmd{service['addr']}"
            default_component = {
                "name": None,
                "object_id": identifier,
                "unique_id": identifier,
                "device": {
                    "identifiers": f"{adapter}_{address}",
                    "name": f"{name}",
                    "suggested_area": f"{room_alias}",
                    "hw_version": device["model"] if device.get("model") and device["model"] else "",
                    "model": device["modelAlias"] if device.get("modelAlias") and device["modelAlias"] else "",
                    "sw_version": f"{adapter}_{address}"
                },
                "state_topic": state_topic
            }
            common_params = {
                "mqtt": mqtt,
                "device": device,
                "state_topic": state_topic,
                "identifier": identifier,
                "default_component": default_component
            }


            # Sensors
            # todo add more sensors: alarm_power?, sensor_power. see old sensor.py
            if service_name in SUPPORTED_SENSORS:
                print(f"- Service: {service_name}")
                status = sensor.new_sensor(**common_params, service_name=service_name)
                if status:
                    statuses.append(status)

            # Meter_elec
            elif service_name == "meter_elec":
                print(f"- Service: {service_name}")
                if device["type"]["type"] == "meter" and \
                        device["type"]["subtype"] == "main_elec": # HAN Meter
                    status = meter_elec.new_han(**common_params, service_name=service_name)
                else:
                    status = meter_elec.new_sensor(**common_params, service_name=service_name)
                if status:
                    for s in status:
                        statuses.append((s[0], s[1]))

            # Door lock
            elif service_name == "door_lock":
                print(f"- Service: {service_name}")
                status = lock.door_lock(**common_params, command_topic=command_topic)
                if status:
                    statuses.append(status)

            # Lights
            elif functionality == "lighting":
                if service_name in SUPPORTED_LIGHTS:
                    print(f"- Service: {service_name}")
                    status = light.new_light(**common_params, service_name=service_name, command_topic=command_topic)
                if status:
                    statuses.append(status)

            # Appliance
            elif functionality == "appliance":
                if service_name == "out_bin_switch":
                    print(f"- Service: {service_name}")
                    status = appliance.new_switch(**common_params, command_topic=command_topic)
                if status:
                    statuses.append(status)

            # Thermostat
            elif service_name == "thermostat":
                print(f"- Service: {service_name}")
                status = thermostat.new_thermostat(**common_params, command_topic=command_topic, devices=devices)
                if status:
                    for s in status:
                        statuses.append((s[0], s[1]))


    # Shortcuts (displayed as buttons)
    print('Creating button devices for shortcuts. FIMP reported %s shortcuts' % (len(shortcuts)))
    for shortcut in shortcuts:
        shortcut_button.new_button(mqtt, shortcut)

    # Mode select (home, away, sleep, vacation)
    status = None
    print('Creating mode select (dropdown). FIMP reported %s mode' % (mode))
    status = mode_select.create(mqtt, mode)
    if status:
        statuses.append(status)


    mqtt.loop()
    time.sleep(2)
    print("Publishing statuses...")
    for state in statuses:
        topic = state[0]
        payload = state[1]
        mqtt.publish(topic, payload)
        print(topic)
    print("Finished pushing statuses...")


def get_adapter_name(device):
    if device["fimp"]["adapter"] == "zwave-ad":
        adapter = "zw"
    elif device["fimp"]["adapter"] == "zigbee":
        adapter = "zb"
    else:
        adapter = device["fimp"]["adapter"]
    return adapter


def get_room_alias(rooms, room_id):
    room_alias = [room["alias"] for room in rooms if room["id"] == room_id][0]
    return room_alias
