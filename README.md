# PZEM-014/016 for Home Assistant

A custom integration for PZEM-014 and PZEM-016 Modbus AC energy meters, for testing through [HACS](https://hacs.xyz)
before it is available in Home Assistant itself.

It reads the meter over a serial RS-485 adapter, or over the network through a
Modbus TCP gateway, and creates one device with six sensors, an alarm, and two settings:

| Sensor | Unit | Notes |
| :--- | :--- | :--- |
| Voltage | V | |
| Current | A | |
| Power | W | |
| Energy | kWh | Stored in Wh by the meter; counts up, so it works in the Energy dashboard |
| Frequency | Hz | |
| Power factor | — | |

| Entity | Type | Notes |
| :--- | :--- | :--- |
| Power alarm | Binary sensor | On while the active power is above the alarm threshold |
| Power alarm threshold | Number (configuration) | In watts, 0 to 65535; written to the meter |
| Modbus address | Number (configuration) | 1 to 247; **disabled by default**, see below |

The measurements are polled every 5 seconds and the settings every 60 seconds
(and straight after you change one).

### Changing the Modbus address

Enabling **Modbus address** lets you move the meter to another address from
Home Assistant, which is handy for giving each meter on a shared RS-485 bus its
own. The meter answers on the new address only, so the integration moves its
config entry to the new address and reloads. An address already used by another
PZEM entry on the same link is refused; one used by some other device on the bus
cannot be detected, so pick a free one.

### Not supported

Resetting the energy counter and factory calibration use manufacturer-specific
Modbus function codes that the Modbus layer Home Assistant uses cannot send. Reset
the counter with the manufacturer's software.

## Requirements

- Home Assistant 2026.10.4 or newer. The integration shares its Modbus
  connection through Home Assistant's own Modbus integration, so the Modbus
  integration does not need to be configured, but it has to be available.
- A meter wired to a serial adapter (RS-485, 9600 baud, 8 data bits, no parity,
  1 stop bit are the meter's defaults), or to a gateway that speaks Modbus TCP.

## Installation

### HACS

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/sambartle/hacs-pzem-014-016` as an **Integration**.
3. Install **PZEM-014/016** and restart Home Assistant.

### Manually

Copy `custom_components/pzem_014_016` into the `custom_components` folder of your
Home Assistant configuration, and restart.

## Configuration

Go to **Settings → Devices & services → Add integration → PZEM-014/016** and choose how
the meter is reached:

- **Serial port (Modbus RTU)**: the serial port, the baud rate (default 9600),
  and the meter's Modbus unit ID (default 1). This also covers a serial port
  that a serial proxy shares over the network.
- **Network (Modbus TCP)**: the host and port (default 502) of the gateway, and
  the meter's unit ID.

The meter is read once before the entry is created, so a wrong port, baud rate
or unit ID is reported straight away. The meter has no serial number, so it is
identified by its link and unit ID: the same meter cannot be added twice.

To change where an existing meter is reached, use **Reconfigure** on the entry.

## Removal

Delete the entry from **Settings → Devices & services**. Remove the
`custom_components/pzem_014_016` folder to uninstall the integration.

## Troubleshooting

- **The adapter is reachable, but the meter did not answer**: check the unit ID,
  the A/B wiring of the RS-485 line, and that the adapter's serial settings match
  the meter's.
- **Entities go unavailable**: the meter stopped answering. They recover on their
  own when it does; nothing needs reloading.
- Enable debug logging for `custom_components.pzem_014_016` and download the
  integration's diagnostics from the device page when reporting an issue. They
  contain the raw registers the meter returned, and leave out the host and port.

## This is a test version of a core integration

The device library, [`pzem-014-016-modbus`](https://github.com/sambartle/pzem-014-016-modbus), is
**vendored**: a copy lives in `custom_components/pzem_014_016/pzem_014_016_modbus`, so installing
this integration needs no extra Python package. Once the integration ships with
Home Assistant, remove this one and set the meter up again, or keep it: a custom
integration with the same domain takes precedence.

### Updating the vendored library

```bash
scripts/vendor                  # from a sibling ../pzem-014-016-modbus checkout
scripts/vendor --pypi 0.1.0     # from a release on PyPI
scripts/vendor --check          # fail if the copy has drifted
```

The `Tests` workflow runs the last one against the release named in
`scripts/vendor.version`, so it needs that release to be on PyPI.

## Development

Open the repository in the dev container (or run `scripts/setup`), then:

| Script | Purpose |
| :--- | :--- |
| `scripts/develop` | Start Home Assistant with this integration, using `config/` |
| `scripts/lint` | Format and lint with Ruff |
| `scripts/test` | Run the tests |
| `scripts/vendor` | Refresh the vendored device library |

The Ruff configuration leaves the vendored library out: it is linted and type
checked in its own repository.

The brand images are not included yet, which is why the HACS validation ignores
`brands`.

## Dependency updates

Renovate (`.github/renovate.json`) is enabled. To use Dependabot instead, rename
`.github/_dependabot.yml` to `.github/dependabot.yml` and delete the Renovate
file.
