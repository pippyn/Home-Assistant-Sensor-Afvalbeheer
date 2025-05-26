# Home Assistant Sensor & Calendar Component for Afvalbeheer

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)

Afvalbeheer provides Home Assistant sensors and a calendar entity for multiple Dutch and Belgian waste collectors using REST APIs.

---

## Supported Waste Collectors

This integration works with many waste collectors, including:

ACV, Afval3xBeter, Afvalstoffendienstkalender, AfvalAlert, Alkmaar, Almere, AlphenAanDenRijn, AreaReiniging, Assen, Avalex, Avri, BAR, Berkelland, Blink, Circulus, Cleanprofs, Cranendonck, Cure (use MijnAfvalwijzer), Cyclus, DAR, DeAfvalApp, DeFryskeMarren, DenHaag, Drimmelen, GAD, Hellendoorn, HVC, Limburg.NET (requires `streetname` and `cityname`), Lingewaard, Meerlanden, Meppel, Middelburg-Vlissingen, MijnAfvalwijzer, Mijnafvalzaken, Montferland, Montfoort, Ôffalkalinder, Omrin, PeelEnMaas, PreZero, Purmerend, RAD, RecycleApp (requires `streetname`), RD4, RWM, Reinis, ROVA, RMN, Saver, Schouwen-Duiveland, Sliedrecht, Spaarnelanden, SudwestFryslan, TwenteMilieu, Venray, Voorschoten, Waalre, Waardlanden, Westland, Woerden, ZRD.

> **Note:** Cure users should switch to MijnAfvalwijzer. Ophaalkalender users should switch to RecycleApp.

---

![Example](https://raw.githubusercontent.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/master/example.png)

---

## Installation

### HACS (Recommended)
- Search for "Afvalbeheer" in HACS and install. Included by default.

### Manual
- Copy the files from `/custom_components/afvalbeheer/` to `[homeassistant]/config/custom_components/afvalbeheer/`.

---

## Features

- **Sensor entities** for each waste type and for upcoming collections (today, tomorrow, next upcoming)
- **Calendar entity** showing all upcoming waste collection events (see below)
- Support for custom naming, icons, translations, and advanced mapping
- Works with both YAML and UI (Config Flow) configuration

---

## Calendar Entity

This integration automatically creates a calendar entity (`calendar.afvalbeheer_<name>`) that shows all upcoming waste collection events for your address and selected waste types. You can use this entity in Home Assistant dashboards, automations, or notifications just like any other calendar.

---

## Configuration Options

Some options can be set via the Home Assistant UI (Config Flow), others only via YAML.

### UI (Config Flow) and YAML Options
- `wastecollector`
- `resources`
- `postcode`
- `streetnumber`
- `suffix`
- `cityname` (Limburg.NET)
- `streetname` (Limburg.NET, RecycleApp)
- `name`
- `nameprefix`
- `dateformat`
- `upcomingsensor`
- `dateonly`
- `dateobject`
- `builtinicons`
- `builtiniconsnew`
- `disableicons`
- `dutch`
- `dayofweek`
- `dayofweekonly`
- `alwaysshowday`

### YAML-Only Options
- `printwastetypes`
- `printwastetypeslugs`
- `updateinterval`
- `customerid`
- `custommapping`
- `addressid`

> **If you need YAML-only options, configure via YAML instead of the UI.**

---

## Example Configuration

### Single Instance
```yaml
afvalbeheer:
  wastecollector: Blink
  resources:
    - restafval
    - gft
    - papier
    - pmd
  postcode: 1111AA
  streetnumber: 1
  suffix: a                        # (optional)
  upcomingsensor: 0                # (optional)
  dateformat: '%d-%m-%Y'           # (optional)
  dateonly: 0                      # (optional)
  name: ""                         # (optional)
  nameprefix: 1                    # (optional)
  builtinicons: 0                  # (optional)
  dutch: 0                         # (optional)
```

### Multiple Instances
```yaml
afvalbeheer:
  - wastecollector: Blink
    resources:
      - restafval
      - gft
      - papier
      - pmd
    postcode: 1111AA
    streetnumber: 1
  - wastecollector: Blink
    resources:
      - restafval
      - gft
      - papier
      - pmd
    postcode: 1111AA
    streetnumber: 2
```

---

## Entity Naming

Sensor and calendar entity names are built as follows:
- If `nameprefix` is enabled (default): `<WasteCollector> <Custom Name> <WasteType>`
- If `nameprefix` is disabled: `<Custom Name> <WasteType>`
- If `name` is empty: `<WasteCollector> <WasteType>`

For example, with `wastecollector: Blink`, `name: Buiten`, and `nameprefix: 1`, you get: `sensor.blink_buiten_restafval`.

---

## Configuration Reference

### Waste Collector
Choose from the supported list above.

### Resources
A list of waste types you want sensors for. At least one is required. Not all types work with all collectors.

**Main options:**
- restafval
- gft
- papier
- pmd

**Other options (collector-dependent):**
- gftgratis, textiel, glas, grofvuil, asbest, apparaten, chemisch, sloopafval, takken, pbd, duobak, restwagen, sortibak

### Address
- `postcode`: Required
- `streetnumber`: Required
- `suffix`: Optional
- `streetname`: Required for Limburg.NET and RecycleApp
- `cityname`: Required for Limburg.NET

### Print All Available Waste Fractions
```yaml
printwastetypes: 1
```
Prints all possible waste fractions for your address/collector in persistent notifications on every HA restart.

### Upcoming Sensor
```yaml
upcomingsensor: 1
```
Adds 3 extra sensors (today, tomorrow, next upcoming) for automations. Default: 0.

### Date Format
```yaml
dateformat: '%d-%m-%Y'
```
All [Python strftime options](http://strftime.org/) are supported. Default: '%d-%m-%Y'.

### Date Only
```yaml
dateonly: 1
```
Removes dayname/today/tomorrow prefix. Default: 0.

### Day of Week
```yaml
dayofweek: 1
```
Adds day name to sensor state if within 7 days. Default: 1.

### Day of Week Only
```yaml
dayofweekonly: 1
```
Removes date if `dayofweek` is active. Default: 0.

### Always Show Day
```yaml
alwaysshowday: 1
```
Removes 7-day limit of `dayofweek`. Default: 0.

### Date Object
```yaml
dateobject: 1
```
Sensor state as a date-time object. Default: 0 (string).

### Name
```yaml
name: 'your custom name'
```
Custom name for the sensor. Useful for multiple sensors.

### Name Prefix
```yaml
nameprefix: 0
```
Removes waste collector name from sensor name. Default: 1.

### Built-in Icons
```yaml
builtinicons: 1
```
Use built-in icons instead of collector icons. Default: 0.

Supported: gft, gftgratis, glas, papier, pmd, pbd, restafval

![Built-in Icons](https://user-images.githubusercontent.com/7591990/196623891-bf169e71-9f65-4d32-bade-befecb1263d8.jpg)

### New Built-in Icons
```yaml
builtiniconsnew: 1
```
Use new built-in icons (requires `builtinicons: 1`). Default: 0.

Supported: gft, gftgratis, glas, papier, pmd, pbd, plastic, zacht-plastic, restafval, kca, textiel, kerstbomen, grofvuil, tuinafval

![New Built-in Icons](https://user-images.githubusercontent.com/7591990/196623742-002840d9-6ecc-4100-9609-1b1f7302f86d.jpg)

### Disable Entity Picture
```yaml
disableicons: 1
```
Disables entity_picture so you can assign MDI icons in customize. Default: 0.

### Translation
```yaml
dutch: 1
```
Display day names in Dutch. Default: 0.

### Update Interval
```yaml
updateinterval: 12
```
Update interval in hours. Default: 12.

### Custom Mapping
```yaml
custommapping:
  keukenafval: VET-goed
  fraction2: New name for fraction2
  papier: Papier (blauw)
  pmd: PMD-Rest
```
Override default mapping for waste fractions. Default: empty.

### Customer ID (Ximmio Commercial Address)
```yaml
customerid: 123456
```
For commercial addresses using Ximmio collectors. Default: empty.

---

## Error Handling

If the integration cannot retrieve data from your waste collector (e.g., due to network issues or API changes), the previous valid data will be kept and a persistent notification may be shown in Home Assistant. Check the Home Assistant logs for more details if you encounter issues.

---

## Credits
- Omrin API - @Jordi1990

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)
