# TP-Link Deco

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Community Forum][forum-shield]][forum]

> ⚠️ **Note**
>
> This fork is **actively maintained**.
>
> Enhancements include real-time Home Assistant events (`tplink_deco_device_event`) when Deco-connected devices join or leave the network. These can be used to automate DNS updates, presence detection, and more.
>
> Maintained by [@ingoratsdorf](https://github.com/ingoratsdorf). Contributions are welcome!
>
> Based on works of [@burrellka](https://github.com/burrellka) which was based on works of [@amosyuen](https://github.com/amosyuen).

## Functionality

This integration is a local polling integration that logs into the admin web UI for TP-Link Deco routers. Currently the only feature implemented is device trackers for active devices.

### Device Trackers

Device trackers are added for both decos and clients. The device tracker state marks whether the device is connected to the deco. If a device is not present, the previous values for attributes are saved except for `down_kilobytes_per_s` and `up_kilobytes_per_s`.

#### Common Attributes

| Attribute       | Example Values (comma separated) |
| --------------- | -------------------------------- |
| mac             | 1A-B2-C3-4D-56-EF                |
| ip_address      | 192.168.0.100                    |
| device_type     | client, deco                     |
| connection_type | wired, band5, band2_4            |

#### Client Attributes

| Attribute            | Example Values (comma separated) |
| -------------------- | -------------------------------- |
| interface            | main, guest                      |
| down_kilobytes_per_s | 10.25                            |
| up_kilobytes_per_s   | 11.75                            |
| deco_device          | living_room                      |
| deco_mac             | 1A-B2-C3-4D-56-EF                |

#### Deco Attributes

| Attribute       | Example Values (comma separated) |
| --------------- | -------------------------------- |
| hw_version      | 2.0                              |
| sw_version      | 1.5.1 Build 20210204 Rel. 50164  |
| device_model    | x60                              |
| internet_online | false, true                      |
| master          | false, true                      |
| bssid_band2_4   | A1:B2:C3:D4:E5:F6                |
| bssid_band5     | A1:B2:C3:D4:E5:F6                |
| signal_band2_4  | 3                                |
| signal_band2_4  | 4                                |
| deco_device     | living_room                      |
| deco_mac        | 1A-B2-C3-4D-56-EF                |

Note: `deco_device` and `deco_mac` will only be set for non-master decos.

### Devices

A device is created for each deco. Each device contains the device_tracker entities for itself and any clients connected to it. Non-master deco devices will indicate that they are connected via the master deco device.

### Services

#### Reboot Deco Service

Reboots the specified decos. Example yaml:

```yaml
service: tplink_deco.reboot_deco
target:
  device_id:
    - ef41562be18e5e3057e232ffb26de9bb
    - d7f96b1f312d83f195b35ecdfbb3b02b
```

{% if not installed %}

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=amosyuen&repository=ha-tplink-deco&category=integration)

### Manual

1. Using the tool of choice open the directory (folder) for your [HA configuration](https://www.home-assistant.io/docs/configuration/) (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `tplink_deco`.
4. Download _all_ the files from the `custom_components/tplink_deco/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant

{% endif %}

## Configuration (Important! Please Read)

Config is done in the HA integrations UI.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tplink_deco)

### Host

The IP address of the main deco which you visit in the browser to see the web admin page. Example: `http://192.168.0.1`. Some decos use https, so if you have trouble connection, try using `https` e.g. `https://192.168.0.1`.

### Login Credentials

The login credentials **MUST** be the deco **owner** credentials and the username should be left as **admin**. Manager credentials will **NOT** work.

Also whenever the owner logs in, all other sessions for the owner will be logged out. So if you log in with the owner credentials in the mobile app, it will cause the integration to be logged out, sometimes resulting in 403 errors. Since the integration has built in retry on auth errors, the integration will re-login, but that will logout your mobile app login session.

Recommend that you create a separate manager account with full permissions to manage the router manually in the mobile app and use the owner credentials only for this integration. If you need to use the owner account to do some manual management, recommend disabling this integration temporarily. Steps to create a manager account:

1. Log out of the deco app
2. Sign up for a new account with a different email address
3. Log out of the deco app
4. Login to original admin account
5. Go to the "More" section and look for "Managers"
6. Add the email address of the new account
7. Log out of the app
8. Login using the new manager account you've just created

### Timeout Secounds

How many seconds to wait until request times out. You can increase this if you get a lot of timeout errors from your router.

Note: The router also has its own timeout so increasing this may not help.

### Timeout Error Retry Count

How many times to retry timeout errors for one request. You can increase this if you get a lot of timeout errors from your router.

### Verify SSL Certificate

Turn off this config option if your browser gives you a warning that the SSL certificate is self-signed when you visit the router host IP in your browser.

### Client Name Prefix

Prefix to prepend to client name. Example: Value of "Client" for "Laptop" client will result in "Client Laptop".

### Client Name Postfix

Postfix to append to client name. Example: Value of "Client" for "Laptop" client will result in "Laptop Client".

### Deco Name Prefix

Prefix to prepend to deco name. Example: Value of "Deco" for "Living Room" deco will result in "Deco Living Room".

### Deco Name Postfix

Postfix to append to deco name. Example: Value of "Deco" for "Living Room" deco will result in "Living Room Deco".

### Disable new entities

If you prefer new entities to be disabled by default:

1. In the Home Assistant (HA) UI go to "Configuration"
2. Click "Integrations"
3. Click the three dots in the bottom right corner fo the TP-Link Deco integration
4. Click "System options"
5. Disable "Enable newly added entities"

## Notify on new entities

Listening to Deco Device Events
You can now respond to devices connecting or disconnecting from your TP-Link Deco mesh network by listening to the tplink_deco_device_event. This event is emitted by the integration whenever a client device joins or leaves the network.

This enables powerful automations such as notifications, DNS updates, access logging, and more — without polling or tracking state manually.

🧪 How to Listen for Device Events
In Developer Tools → Events, type tplink_deco_device_event into the "Listen to events" box and click "Start Listening". Then, connect or disconnect a device to your Deco network. You should see event data like the following:

```json
{
  "event_type": "tplink_deco_device_event",
  "data": {
    "mac": "DA-2D-3D-11-24-A7",
    "name": "KEVIN-s-S24-Ultra _deco_Client",
    "state": "connected"
  }
}
```

The state can be "connected" or "disconnected" depending on the event.

📲 Notify When a Device Connects to Deco Wi-Fi
This automation will send a mobile notification when any Deco-connected client comes online:

```yaml
- alias: Notify When Deco Device Connects
  mode: parallel
  max: 100

  trigger:
    - platform: event
      event_type: tplink_deco_device_event
      event_data:
        state: connected

  variables:
    name: "{{ trigger.event.data.name }}"
    mac: "{{ trigger.event.data.mac }}"

  action:
    - service: notify.mobile_app_yourdevice
      data:
        title: "{{ name or mac }} connected to Wi-Fi"
        message: "{{ name or mac }} just joined your Deco network."
        data:
          group: wifi-new-device
```

📴 Notify When a Device Disconnects
Similarly, this automation notifies you when a client disconnects:

```jaml
- alias: Notify When Deco Device Disconnects
  mode: parallel
  max: 100

  trigger:
    - platform: event
      event_type: tplink_deco_device_event
      event_data:
        state: disconnected

  variables:
    name: "{{ trigger.event.data.name }}"
    mac: "{{ trigger.event.data.mac }}"

  action:
    - service: notify.mobile_app_yourdevice
      data:
        title: "{{ name or mac }} disconnected"
        message: "{{ name or mac }} has disconnected from your Deco Wi-Fi."
        data:
          group: wifi-lost-device
```

🧠 Pro Tip: Trigger Other Automations
You can also use this event to:

Log connections to a file

Auto-update custom DNS entries (e.g., with Pi-hole)

Restrict internet access or trigger parental control

Toggle smart switches or other entities based on presence

For example, to trigger a Pi-hole DNS entry injection, your automation might call a rest_command that sends the hostname/IP pair to an internal service.

Trigger External Action When Deco Device Connects
This integration emits the tplink_deco_device_event whenever a client device connects or disconnects from your Deco mesh network.

You can use this event to trigger automations, notify users, or send data to an external service or API.

📡 Event Format
The event name is tplink_deco_device_event and includes the following data:

```json
{
  "mac": "DA-2D-3D-11-24-A7",
  "name": "John-iPhone_deco_Client",
  "state": "connected"
}
```

Possible values for state:

"connected"

"disconnected"

⚡ Example: Send Device Connection Info to an External API
This automation listens for Deco connection events and sends a GET request to a custom HTTP endpoint when a client joins the network:

```yaml
- alias: Notify external system when Deco client connects
  description: Trigger an API call when a Deco-connected device joins the network
  trigger:
    - platform: event
      event_type: tplink_deco_device_event
      event_data:
        state: connected

  variables:
    ip: "{{ state_attr('device_tracker.' ~ trigger.event.data.name | lower | replace(' ', '_'), 'ip') }}"
    hostname: "{{ trigger.event.data.name | lower | replace(' ', '-') | regex_replace('[^a-z0-9-]', '') }}"

  condition:
    - "{{ ip is defined and ip.startswith('192.168.') }}"

  action:
    - service: rest_command.notify_external_service
      data:
        ip: "{{ ip }}"
        hostname: "{{ hostname }}"
    - service: logbook.log
      data:
        name: External Integration Triggered
        message: "Sent {{ hostname }} -> {{ ip }} to external system"

  mode: queued
```

You’ll also need this REST command in your configuration.yaml or set via the UI:

```yaml
rest_command:
  notify_external_service:
    url: "http://your-api-endpoint.local/notify?ip={{ ip }}&hostname={{ hostname }}"
    method: GET
```

📝 Replace the URL above with the endpoint of your own service or integration.

## Tested Devices

- Deco M4
- Deco M5
- Deco M9 Plus
- Deco P7
- Deco P9
- Deco PX50
- Deco S4
- Deco X20
- Deco X50
- Deco X60
- Deco X68
- Deco X73-DSL(1.0)
- Deco XE75
- Deco X90
- Mercusys Halo H70X
- Mercusys Halo H80X

## Not Working Devices

- Deco S7 (1.3.0 Build 20220609 Rel. 64814)

## Known Issues

### Timeout Error

Some routers give a lot of timeout errors like `Timeout fetching tplink_deco`, which cause the devices to be unavailable. This is a problem with the router. Potential mitigations:

- Rebooting the router
- Increasing [timeout seconds](#timeout-seconds) in integration config
- Increasing [timeout error retry count](#timeout-error-retry-count) in integration config

### Extra Devices

You may see extra devices show up under the Tp-Link deco integration as per https://github.com/amosyuen/ha-tplink-deco/issues/73. This is expected because the entities use macs for their unique ID. If there is another integration that exposes the same device using their mac, Home Assistant will combine the info from devices that have the same unique ID. This is working as intended since they represent the same device.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](https://github.com/ingoratsdorf/ha-tplink-deco/blob/main/CONTRIBUTING.md)

## Credits

Forked from [@amosyuen](https://github.com/amosyuen/ha-tplink-deco) who has done an amazing work with this. All credit to them.
Integrated events by [@burrellka](https://github.com/burrellka).
Added Slavic language translation by [@misa1515](https://github.com/misa1515/ha-tplink-deco/activity?ref=patch-5)

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[buymecoffee]: https://paypal.me/amosyuen
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/amosyuen/ha-tplink-deco.svg?style=for-the-badge
[commits]: https://github.com/ingoratsdorf/ha-tplink-deco/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/amosyuen/ha-tplink-deco.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40amosyuen-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/amosyuen/ha-tplink-deco.svg?style=for-the-badge
[releases]: https://github.com/ingoratsdorf/ha-tplink-deco/releases
[user_profile]: https://github.com/amosyuen
