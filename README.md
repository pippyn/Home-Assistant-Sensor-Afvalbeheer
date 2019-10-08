## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch waste collectors using REST API.
This sensor works with the following waste collectors: Blink, Cure, Cyclus, DAR, HVC Groep, Meerlanden, RMN (Reinigingsbedrijf Midden Nederland), Peel en Maas, Circulus-Berkel (Afvalvrij), Avalex, Venray, Den Haag, Berkelland, Alphen aan den Rijn, Waalre, ZRD, Spaarnelanden, Montfoort, GAD and Cranendonck.

### Install:
Copy the files in the /custom_components/afvalbeheer/ folder to: [homeassistant]/config/custom_components/afvalbeheer/

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
      nameprefix: 1                    (optional)
      builtinicons: 0                  (optional)
      dutch: 0                         (optional)
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
  - PeelEnMaas
  - RMN
  - Spaarnelanden
  - Venray
  - Waalre
  - ZRD

### Resources
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
  - kca
  - pbd

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

### Name prefix
```yaml
nameprefix: 0
```
If you don't want to add the waste collecoctors name to the sensor name. Default is 1.

### Built in icons
```yaml
builtinicons: 1
```
If you don't want to use the icons from your waste collector you can use the built in icons. Default is 0.
For now only these fractions are supported:
- gft
- gftgratis
- glas
- papier
- pmd
- pbd
- restafval

### Name prefix
```yaml
dutch: 1
```
If you want to display the names of the days in dutch. Default is 0.

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

