# TVHeadend Tuner Monitor — Home Assistant Integration

A custom Home Assistant integration that monitors your local TVHeadend instance, reports the connectivity state of every DVB tuner, exposes signal-quality metrics, and provides a one-click restart button.

---

## Features

| Entity type | What it does |
|---|---|
| **Binary sensor** (per tuner) | `ON` = tuner connected & healthy, `OFF` = missing / disabled |
| **Sensor – Signal Strength** | Signal level in % (relative) or dB (absolute), per tuner |
| **Sensor – SNR** | Signal-to-noise ratio per tuner |
| **Sensor – BER** | Bit-error rate per tuner |
| **Sensor – Uncorrected Blocks** | UNC counter per tuner |
| **Sensor – Active Subscriptions** | Live recordings / streams on that tuner |
| **Sensor – Total Tuners** | Total adapters known to TVHeadend |
| **Sensor – Connected Tuners** | How many are currently healthy |
| **Sensor – Server Version** | TVHeadend software version string |
| **Button – Restart TVHeadend** | Calls a `shell_command` to restart the service |

---

## Requirements

- Home Assistant 2023.x or newer
- TVHeadend 4.2 or 4.3 running locally (HTTP API must be reachable)
- Network access from HA to TVHeadend (default port **9981**)

---

## Installation

### Option 1 – HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories.
2. Add your repo URL, category **Integration**.
3. Install **TVHeadend Tuner Monitor** and restart HA.

### Option 2 – Manual

1. Copy the `custom_components/tvheadend_tuner/` folder into your HA config directory:
   ```
   <config>/custom_components/tvheadend_tuner/
   ```
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **TVHeadend Tuner Monitor**.
3. Fill in:
   - **Host** – IP address or hostname of your TVHeadend server (e.g. `192.168.1.10`)
   - **Port** – default `9981`
   - **Username / Password** – leave blank if TVHeadend has no auth
   - **Scan interval** – how often to poll (default 30 s, min 10 s)

---

## Enabling the Restart Button

TVHeadend has no HTTP restart endpoint, so the restart button uses Home Assistant's `shell_command` integration.

### If HA runs on the **same host** as TVHeadend (bare-metal / venv):

Add to `configuration.yaml`:
```yaml
shell_command:
  restart_tvheadend: "sudo systemctl restart tvheadend"
```

You may need to allow the `homeassistant` user to run this without a password:
```
# /etc/sudoers.d/ha-tvheadend
homeassistant ALL=(ALL) NOPASSWD: /bin/systemctl restart tvheadend
```

### If TVHeadend runs in **Docker**:

```yaml
shell_command:
  restart_tvheadend: "docker restart tvheadend"
```

(Replace `tvheadend` with your actual container name.)

### If TVHeadend is on a **different host** (SSH):

```yaml
shell_command:
  restart_tvheadend: "ssh user@192.168.1.10 'sudo systemctl restart tvheadend'"
```

After editing `configuration.yaml`, go to **Developer Tools → YAML → Reload Shell Command**.

---

## Example Automations

### Alert when a tuner disconnects

```yaml
automation:
  - alias: "Notify when DVB tuner disconnects"
    trigger:
      - platform: state
        entity_id: binary_sensor.adapter_0_frontend_0_connected
        to: "off"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "⚠️ DVB tuner disconnected! Check the USB connection."
```

### Auto-restart TVHeadend if all tuners drop

```yaml
automation:
  - alias: "Restart TVHeadend if all tuners lost"
    trigger:
      - platform: numeric_state
        entity_id: sensor.tvheadend_connected_tuners
        below: 1
        for: "00:02:00"
    action:
      - service: button.press
        target:
          entity_id: button.restart_tvheadend
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Cannot connect" during setup | Check host/port, firewall, and that TVHeadend is running |
| All tuners show disconnected | Check TVHeadend → Configuration → DVB Inputs; adapters must be enabled |
| Signal values are 0 | Tuner is idle (no active subscription); values are only live when tuning |
| Restart button shows notification instead of restarting | Follow the shell_command setup steps above |

---

## File structure

```
custom_components/tvheadend_tuner/
├── __init__.py          # Integration setup / teardown
├── manifest.json        # Integration metadata
├── strings.json         # UI strings
├── const.py             # Constants
├── config_flow.py       # UI-driven config & options flow
├── coordinator.py       # DataUpdateCoordinator (polling)
├── tvheadend.py         # Async TVHeadend HTTP API client
├── binary_sensor.py     # Tuner connected/disconnected sensors
├── sensor.py            # Signal quality + aggregate sensors
└── button.py            # Restart button
```
