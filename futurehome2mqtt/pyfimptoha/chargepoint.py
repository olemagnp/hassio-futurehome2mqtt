import json
import typing

uuid_gen = """
{%- macro unique_id() -%}
{%- set ns = namespace(uuid = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx') %}
{%- set ns.new_uuid = '' -%}
{%- for x in ns.uuid -%}
 {%- set ns.new_uuid = [ns.new_uuid,(x | replace('x', [0,1,2,3,4,5,6,7,8,9,'a','b','c','d','e','f'] | random ))] | join %}
{%- endfor -%}
{{ ns.new_uuid }}
{%- endmacro -%}
"""


def new_chargepoint(
    mqtt,
    device: typing.Any,
    state_topic,
    identifier,
    default_component,
    command_topic,
):
    supported_max_current = device["services"]["chargepoint"]["props"][
        "sup_max_current"
    ]

    chargepoint_device = {
        "device": default_component["device"],
        "o": {
            "name": "Futurehome2MQTT",
        },
        "state_topic": state_topic,
        "command_topic": command_topic,
        "cmps": {
            "start_charging": start_charging_component(identifier, state_topic),
            "stop_charging": stop_charging_component(identifier, state_topic),
            "cable_lock": cable_lock_component(identifier),
            "state": state_component(
                identifier,
                device["services"]["chargepoint"]["props"]["sup_states"],
                state_topic,
            ),
            "current_session": current_session_component(identifier, state_topic),
            "max_current": max_current_component(identifier, supported_max_current),
            "session_offered_current": session_offered_current_component(
                identifier, supported_max_current
            ),
            "phase_mode": phase_mode_component(
                identifier,
                device["services"]["chargepoint"]["props"]["sup_phase_modes"],
            ),
        },
    }

    payload = json.dumps(chargepoint_device)

    mqtt.publish(f"homeassistant/device/{identifier}/config", payload)

    # STATUSES
    statuses: list[tuple[str, str]] = []

    cable_lock_status_payload = {
        "serv": "chargepoint",
        "type": "cmd.cable_lock.get_report",
        "val_t": "null",
        "val": None,
        "src": "homeassistant",
    }

    state_status_payload = {
        "serv": "chargepoint",
        "type": "cmd.state.get_report",
        "val_t": "null",
        "val": None,
        "src": "homeassistant",
    }

    current_session_status_payload = {
        "serv": "chargepoint",
        "type": "cmd.current_session.get_report",
        "val_t": "null",
        "val": None,
        "src": "homeassistant",
    }

    max_current_status_payload = {
        "serv": "chargepoint",
        "type": "cmd.max_current.get_report",
        "val_t": "null",
        "val": None,
        "src": "homeassistant",
    }
    phase_mode_status_payload = {
        "serv": "chargepoint",
        "type": "cmd.phase_mode.get_report",
        "val_t": "null",
        "val": None,
        "src": "homeassistant",
    }

    statuses.append((command_topic, json.dumps(cable_lock_status_payload)))
    statuses.append((command_topic, json.dumps(state_status_payload)))
    statuses.append((command_topic, json.dumps(current_session_status_payload)))
    statuses.append((command_topic, json.dumps(max_current_status_payload)))
    statuses.append((command_topic, json.dumps(phase_mode_status_payload)))

    return statuses


def state_component(identifier, supported_states: list[str], attribute_topic: str):
    return {
        "name": "Charger state",
        "platform": "sensor",
        "unique_id": f"{identifier}_state",
        "device_class": "enum",
        "options": supported_states,
        "json_attributes_template": """
            {% if value_json.type == 'evt.state.report' and value_json.props != None %}
                {{ value_json.props }}
            {% else %}
                {}
            {% endif %}
        """,
        "json_attributes_topic": attribute_topic,
        "value_template": """
            {% if value_json.type == 'evt.state.report' %}
                {{ value_json.val }}
            {% else %}
                {{ this.state }}
            {% endif %}
        """,
    }


def cable_lock_component(identifier):
    return {
        "name": "Cable Lock",
        "icon": "mdi:lock",
        "platform": "switch",
        "unique_id": f"{identifier}_cable_lock",
        "device_class": "switch",
        "payload_on": True,
        "payload_off": False,
        "command_template": f"""
                    {uuid_gen}
                    {{
                        "serv": "chargepoint",
                        "type": "cmd.cable_lock.set",
                        "val_t": "bool",
                        "val": {{{{ value | lower }}}},
                        "tags": [],
                        "src": "homeassistant",
                        "ver": "1",
                        "ctime": "{{{{ now().isoformat() }}}}",
                        "uid": "{{{{unique_id()}}}}"
                    }}
                """,
        "state_on": "on",
        "state_off": "off",
        "value_template": """
            {% if value_json.type == 'evt.cable_lock.report' %}
                {{ 'on' if value_json.val else 'off' }}
            {% else %}
                {{ this.state }}
            {% endif %}
                """,
    }


def start_charging_component(identifier, state_topic: str):
    return {
        "name": "Start charging",
        "platform": "button",
        "unique_id": f"{identifier}_start_charging",
        "availability_topic": state_topic,
        "availability_template": """
            {% if value_json.type == 'evt.state.report' %}
                {{ 'online' if value_json.val == 'ready_to_charge' else 'offline' }}
            {% else %}
                {{ 'online' if this.state != 'unavailable' else 'offline' }}
            {% endif %}
        """,
        "payload_press": json.dumps(
            {
                "serv": "chargepoint",
                "type": "cmd.charge.start",
                "val_t": "null",
                "val": None,
                "src": "homeassistant",
            }
        ),
    }


def stop_charging_component(identifier, state_topic: str):
    return {
        "name": "Stop charging",
        "platform": "button",
        "unique_id": f"{identifier}_stop_charging",
        "availability_topic": state_topic,
        "availability_template": """
            {% if value_json.type == 'evt.state.report' %}
                {{ 'online' if value_json.val == 'charging' else 'offline' }}
            {% else %}
                {{ 'online' if this.state != 'unavailable' else 'offline' }}
            {% endif %}
        """,
        "payload_press": json.dumps(
            {
                "serv": "chargepoint",
                "type": "cmd.charge.stop",
                "val_t": "null",
                "val": None,
                "src": "homeassistant",
            }
        ),
    }


def current_session_component(identifier, attribute_topic):
    return {
        "name": "Current session",
        "platform": "sensor",
        "unique_id": f"{identifier}_current_session",
        "device_class": "energy",
        "state_class": "TOTAL_INCREASING",
        "unit_of_measurement": "kWh",
        "suggested_display_precision": 2,
        "json_attributes_template": """
            {% if value_json.type == 'evt.current_session.report' and value_json.props != None %}
                {{ value_json.props | tojson }}
            {% else %}
                {
                    "offered_current": {{ state_attr(name, "offered_current") if state_attr(name, "offered_current") is not none else 'null' }},
                    "started_at": {{ state_attr(name, "started_at") if state_attr(name, "started_at") is not none else 'null' }},
                    "finished_at": {{ state_attr(name, "finished_at") if state_attr(name, "finished_at") is not none else 'null' }},
                    "previous_session": {{ state_attr(name, "previous_session") if state_attr(name, "previous_session") is not none else 'null' }}
                }
            {% endif %}
        """,
        "json_attributes_topic": attribute_topic,
        "value_template": """
            {% if value_json.type == 'evt.current_session.report' %}
                {{ value_json.val }}
            {% elif this.state != 'unknown' %}
                {{ this.state }}
            {% else %}
                0
            {% endif %}
        """,
    }


def max_current_component(identifier, supported_max_current: int):
    return {
        "name": "Max current",
        "unique_id": f"{identifier}_max_current",
        "platform": "number",
        "command_template": """
            {
                "serv": "chargepoint",
                "type": "cmd.max_current.set",
                "val_t": "int",
                "val": {{ value }},
                "src": "homeassistant"
            }
    """,
        "device_class": "current",
        "min": 6,
        "max": supported_max_current,
        "unit_of_measurement": "A",
        "value_template": """
            {% if value_json.type == 'evt.max_current.report' %}
                {{ value_json.val }}
            {% elif this.state != 'unknown' %}
                {{ this.state }}
            {% else %}
                6
            {% endif %}
        """,
    }


def session_offered_current_component(identifier, supported_max_current: int):
    return {
        "name": "Current session offered current",
        "unique_id": f"{identifier}_session_offered_current",
        "platform": "number",
        "command_template": """
            {
                "serv": "chargepoint",
                "type": "cmd.current_session.set_current",
                "val_t": "int",
                "val": {{ value }},
                "src": "homeassistant"
            }
    """,
        "device_class": "current",
        "min": 0,
        "max": supported_max_current,
        "value_template": """
            {% if value_json.type == 'evt.current_session.report' %}
                {% if value_json.props is not none  %}
                    {{ value_json.props.offered_current }}
                {% else %}
                    0
                {% endif %}
            {% else %}
                {{ this.state if this.state != 'unknown' else 0 }}
            {% endif %}
        """,
    }


def phase_mode_component(identifier, supported_phase_modes):
    return {
        "name": "Phase mode",
        "unique_id": f"{identifier}_phase_mode",
        "platform": "select",
        "command_template": """
            {
                "serv": "chargepoint",
                "type": "cmd.phase_mode.set",
                "val_t": "string",
                "val": "{{ value }}",
                "src": "homeassistant"
            }
    """,
        "options": supported_phase_modes,
        "value_template": f"""
            {{% if value_json.type == 'evt.phase_mode.report' %}}
                {{{{ value_json.val }}}}
            {{% elif this.state != 'unknown' %}}
                {{{{ this.state }}}}
            {{% else %}}
                {supported_phase_modes[0]}
            {{% endif %}}
        """,
    }
