## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch waste collectors using REST API.
This sensor works with the following waste collectors: Blink, Cure, Cyclus, DAR, HVC Groep, Meerlanden and RMN (Reinigingsbedrijf Midden Nederland)

![alt text](https://github.com/pippyn/Home-Assisant-Sensor-Cure-Afvalbeheer/blob/master/example.png)

### Install:
- Copy the afvalbeheer.py file to: [homeassistant]/config/custom_components/sensor/
- Example config:

```yaml
  sensor:
    - platform: afvalbeheer
      wastcollector: Bink
      resources:                      # (at least 1 required)
        - restafval
        - gft
        - papier
        - pmd
      postcode: 1111AA                # (required)
      streetnumber: 1                 # (required)
```
### Wastcollector
```
wastcollector:
```
Choose your collector from this list:
  - Blink
  - Cure
  - Cyclus
  - DAR
  - HVC
  - Meerlanden
  - RMN

### Recourses
```
resources:
```
This is a list of fractions you want a sensor for. At least one option is required. Not all fractions work with all collectors.
Main resources options:
  - restafval
  - gft
  - papier
  - pmd

Some collectors also use some of these options:
  - gftgratis
  - textiel
  - glas
  - grofvuil
  - asbest
  - apparaten
  - chemisch
  - sloopafval
  - takken

### Postcode
Postcode is required and is your own postcode

### Street number
Street number is required and is your own street number

## Custom updater
You can use the custom updater with this sensor
```yaml
custom_updater:
  track:
    - components
  component_urls:
    - https://raw.githubusercontent.com/pippyn/Home-Assisant-Sensor-Afvalbeheer/master/custom_components.json
```
