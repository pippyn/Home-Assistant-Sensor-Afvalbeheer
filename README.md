# Home Assistant Sensor & Calendar Component for Afvalbeheer

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)

Afvalbeheer provides Home Assistant sensors and a calendar entity for multiple Dutch and Belgian waste collectors using REST APIs.

> **⚠️ Important Notice:** YAML configuration is deprecated as of v6.0.0. All new installations and configurations should use the Home Assistant UI (Config Flow). Existing YAML configurations will automatically be imported and should be removed form configuration.yaml after migration.

---

## Supported Waste Collectors

This integration works with many waste collectors, including:

ACV, Afval3xBeter, Afvalstoffendienstkalender, AfvalAlert, Alkmaar, Almere, AlphenAanDenRijn, AreaReiniging, Assen, Avalex, Avri, BAR, Berkelland, Blink, Circulus, Cleanprofs, Cranendonck, Cure (use MijnAfvalwijzer), Cyclus, DAR, DeAfvalApp, DeFryskeMarren, DenHaag, Drimmelen, GAD, Hellendoorn, HVC, Irado, Limburg.NET (requires `streetname` and `cityname`), Lingewaard, Maassluis, Meerlanden, Meppel, Middelburg-Vlissingen, MijnAfvalwijzer, Mijnafvalzaken, Montferland, Montfoort, Nijkerk Ôffalkalinder, Omrin, OudeIJsselstreek, PeelEnMaas, PreZero, Purmerend, RAD, RecycleApp (requires `streetname`), RD4, RWM, Reinis, ROVA, RMN, Saver, Schouwen-Duiveland, Sliedrecht, Spaarnelanden, SudwestFryslan, Tilburg, TwenteMilieu, Uithoorn, Venray, Voorschoten, Waalre, Waardlanden, Westland, Woerden, ZRD, Groningen.

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
- Easy configuration through Home Assistant UI (Config Flow)

---

## Calendar Entity

This integration automatically creates a calendar entity (`calendar.afvalbeheer_<name>`) that shows all upcoming waste collection events for your address and selected waste types. You can use this entity in Home Assistant dashboards, automations, or notifications just like any other calendar.

---

## Configuration

### Adding the Integration (Recommended)

1. Go to **Settings** → **Devices & Services** in Home Assistant
2. Click **Add Integration** and search for "Afvalbeheer"
3. Follow the multi-step configuration wizard:
   - **Step 1:** Select your waste collector from the dropdown
   - **Step 2:** Enter your address details (postcode, street number, and suffix if applicable)
   - **Step 3:** Select which waste types you want sensors for
   - **Step 4:** Configure display options (date format, icons, naming, etc.)

All configuration options are available through the UI, including:
- Waste collector selection
- Address information (postcode, street number, suffix)
- Special address fields (streetname for RecycleApp/Limburg.NET, cityname for Limburg.NET)
- Waste type selection from available resources
- Display options (date format, upcoming sensors, icons, Dutch translation)
- Custom naming and prefixes

### Multiple Instances

To set up multiple instances (e.g., for different addresses), simply add the integration multiple times through the UI. Each instance will have its own set of sensors and calendar entity with unique naming based on your configuration.

---

## YAML Configuration (Deprecated)

> **⚠️ YAML configuration is deprecated as of v6.0.0** and will be removed in a future version. Please migrate to Config Flow (UI configuration) for new installations.

<details>
<summary>Click to view legacy YAML configuration examples</summary>

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
</details>

---

## Entity Naming

### Sensor Entities
Sensor names are built as: `[WasteCollector] [CustomName] WasteType`
- If **Name Prefix** is enabled (default): `WasteCollector CustomName WasteType`
- If **Name Prefix** is disabled: `CustomName WasteType`  
- If **Custom Name** is empty: `WasteCollector WasteType`

Examples:
- With waste collector "Blink", custom name "Buiten", name prefix enabled: `sensor.blink_buiten_restafval`
- With waste collector "Blink", no custom name, name prefix enabled: `sensor.blink_restafval`
- With custom name "Buiten", name prefix disabled: `sensor.buiten_restafval`

### Calendar Entity
Calendar names are always: `Afvalbeheer WasteCollector`
- Example: `calendar.afvalbeheer_blink`

---

## Configuration Options Reference

All configuration options are available through the Home Assistant UI (Config Flow). Here's what each option does:

### Waste Collector
Choose from the supported list above. This determines which API the integration will use to fetch your waste collection data.

### Address Information
- **Postcode**: Required for all collectors
- **Street Number**: Required for all collectors  
- **Suffix**: Optional (e.g., "a", "bis")
- **Street Name**: Required for Limburg.NET and RecycleApp collectors
- **City Name**: Required for Limburg.NET collector

### Waste Types (Resources)
Select which waste types you want sensors for. At least one is required. Available options depend on your collector:

**Common types:**
- restafval (residual waste)
- gft (organic waste)
- papier (paper)
- pmd (plastic/metal/drink cartons)

**Additional types (collector-dependent):**
- gftgratis, textiel, glas, grofvuil, asbest, apparaten, chemisch, sloopafval, takken, pbd, duobak, restwagen, sortibak

### Display Options

- **Upcoming Sensor**: Adds 3 extra sensors (today, tomorrow, next upcoming) for automations
- **Date Format**: Customize how dates are displayed using [Python strftime options](http://strftime.org/). Default: '%d-%m-%Y'
- **Date Only**: Remove day name/today/tomorrow prefix from sensor states
- **Day of Week**: Add day name to sensor state if collection is within 7 days
- **Day of Week Only**: Show only day name when `Day of Week` is enabled
- **Always Show Day**: Remove 7-day limit for showing day names
- **Date Object**: Return sensor state as date-time object instead of string

### Naming Options

- **Name**: Custom name for your sensors (useful for multiple instances)
- **Name Prefix**: Include waste collector name in sensor names (enabled by default)

### Icon Options

- **Built-in Icons**: Use integration's built-in icons instead of collector-provided icons
- **New Built-in Icons**: Use newer icon set (requires Built-in Icons enabled)
- **Disable Icons**: Disable entity pictures to use custom MDI icons

**Built-in Icons:**

![Built-in Icons](https://user-images.githubusercontent.com/7591990/196623891-bf169e71-9f65-4d32-bade-befecb1263d8.jpg)

**New Built-in Icons:**

![New Built-in Icons](https://user-images.githubusercontent.com/7591990/196623742-002840d9-6ecc-4100-9609-1b1f7302f86d.jpg)

### Language Options

- **Dutch**: Display day names in Dutch instead of English

---

## Error Handling

If the integration cannot retrieve data from your waste collector (e.g., due to network issues or API changes), the previous valid data will be kept and a persistent notification may be shown in Home Assistant. Check the Home Assistant logs for more details if you encounter issues.

---

## Credits
- Omrin API - @Jordi1990

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)
