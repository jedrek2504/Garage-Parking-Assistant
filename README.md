# Garage Parking Assistant

Smart parking assistant for Raspberry Pi with ultrasonic sensors, LED strip, camera, and Home Assistant integration.

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/jedrek2504/Garage-Parking-Assistant.git
cd Garage-Parking-Assistant
````

### 2. Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Home Assistant

* Run Home Assistant in Docker (see [Home Assistant docs](https://www.home-assistant.io/installation/linux)).
* Copy configuration files from this repo (`configuration.yaml`, `automations.yaml`) into your Home Assistant config directory.
* (Optional) To use the same dashboard view, create a new dashboard in Home Assistant and paste the contents of `dashboard.yaml` into the **Raw configuration editor**.

### 5. Run as a service

To enable auto-start on boot, use the provided `start.sh` and `garage-parking-assistant.service`:

```bash
sudo cp start.sh /usr/local/bin/
sudo cp systemd/garage-parking-assistant.service /etc/systemd/system/
sudo systemctl enable garage-parking-assistant
sudo systemctl start garage-parking-assistant
```
