## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch waste collectors using REST API.
This sensor works with the following waste collectors: Blink, Cure, Cyclus, DAR, HVC Groep, Meerlanden, RMN (Reinigingsbedrijf Midden Nederland), Circulus-Berkel (Afvalvrij), Avalex, Venray, Den Haag, Berkelland, Alphen aan den Rijn, Waalre, ZRD, Spaarnelanden, Montfoort, GAD and Cranendonck.

![alt text](https://github.com/pippyn/Home-Assisant-Sensor-Cure-Afvalbeheer/blob/master/example.png)

### Install:
#### Home assistant 88 and higher:
- Copy the afvalbeheer.py file to: [homeassistant]/config/custom_components/afvalbeheer/sensor.py
#### Before Home assistant 88:
- Copy the afvalbeheer.py file to: [homeassistant]/config/custom_components/sensor/afvalbeheer.py

Example config:

```yaml
  sensor:
    - platform: afvalbeheer
      wastecollector: Blink            (required)
      resources:                       (at least 1 required)
        - restafval
        - gft
        - papier
        - pmd
      postcode: 1111AA                 (required)
      streetnumber: 1                  (required)
      upcomingsensor: 0                (optional)
      dateformat: '%d-%m-%Y'           (optional)
      dateonly: 0                      (optional)
```
### Wastecollector
```
wastecollector:
```
Choose your collector from this list:
  - AlphenAanDenRijn
  - Avalex
  - Berkelland
  - Blink
  - Circulus-Berkel
  - Cranendonck
  - Cure
  - Cyclus
  - DAR
  - DenHaag
  - GAD
  - HVC
  - Meerlanden
  - Montfoort
  - RMN
  - Spaarnelanden
  - Venray
  - Waalre
  - ZRD

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

### Upcoming sensor
```yaml
upcomingsensor: 1
```
If you activate this option you'll get 2 extra sensors (today and tomorrow) which are handy for automations. 
The today sensor will display the fractions collected today.
The tomorrow sensor will display the fractions collected tomorrow.
Default is 0.

### Date format
```yaml
dateformat:
```
If you want to adjust the way the date is presented. You can do it using the dateformat option. All [python strftime options](http://strftime.org/) should work.
Default is '%d-%m-%Y', which will result in per example: 
```yaml
21-9-2019.
```
If you wish to remove the year and the dashes and want to show the name of the month abbreviated, you would provide '%d %b'. Which will result in: 
```yaml
21 Sep
```

### Date only
```yaml
dateonly: 1
```
If you don't want to add dayname, tomorrow or today in front of date activate this option. Default is 0.

## Custom updater
You can use the custom updater with this sensor

Home assistant 88 and higher:
```yaml
custom_updater:
  track:
    - components
  component_urls:
    - https://raw.githubusercontent.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/master/custom_components.json
```
Before Home assistant 88:
```yaml
custom_updater:
  track:
    - components
  component_urls:
    - https://raw.githubusercontent.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/master/custom_components_old.json
```
