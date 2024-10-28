[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)
## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch and Belgium waste collectors using REST API.
This sensor works with the following waste collectors: Blink, Cure, Suez, ACV, TwenteMilieu, Hellendoorn, Cyclus, DAR, De Fryske Marren, HVC Groep, Meerlanden, RMN (Reinigingsbedrijf Midden Nederland), Schouwen-Duiveland, Peel en Maas, Purmerend, Circulus-Berkel (Afvalvrij), Avalex, Venray, Den Haag, Berkelland, Alphen aan den Rijn, Waalre, ZRD, Spaarnelanden, SudwestFryslan, Montfoort, GAD, Cranendonck, ROVA, RD4, RWM, Limburg.NET, Afval Alert, RecycleApp, DeAfvalApp, Alkmaar, AreaReiniging, Almere, Waardlanden, Reinis, Avri, Omrin, BAR, Assen, RAD, Meppel, Montferland, PreZero, Sliedrecht, Lingewaard Voorschoten, Westland, Ôffalkalinder, Afval3xBeter, Middelburg-Vlissingen and Cleanprofs.

Cure users should switch to the waste collector MijnAfvalwijzer

Ophaalkalender users should switch to the waste collector RecycleApp

![alt text](https://raw.githubusercontent.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/master/example.png)

## Install:
### HACS
You can use HACS to install this sensor. It is included by default.
### Manual
Copy the files in the /custom_components/afvalbeheer/ folder to: [homeassistant]/config/custom_components/afvalbeheer/

## Example configs:
### Single instance
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
### Multiple instances
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
### Wastecollector
```
wastecollector:
```
Choose your collector from this list:
  - ACV
  - Afval3xBeter
  - Afvalstoffendienstkalender
  - AfvalAlert
  - Alkmaar
  - Almere
  - AlphenAanDenRijn
  - AreaReiniging
  - Assen
  - Avalex
  - Avri
  - BAR
  - Berkelland
  - Blink
  - Circulus
  - Cleanprofs
  - Cranendonck
  - Cure (use MijnAfvalwijzer)
  - Cyclus
  - DAR
  - DeAfvalApp
  - DeFryskeMarren
  - DenHaag
  - GAD
  - Hellendoorn
  - HVC
  - Limburg.NET (don't forget the streetname and cityname option)
  - Lingewaard
  - Meerlanden
  - Meppel
  - Middelburg-Vlissingen
  - MijnAfvalwijzer
  - Mijnafvalzaken
  - Montferland
  - Montfoort
  - Ôffalkalinder
  - Omrin
  - PeelEnMaas
  - PreZero
  - Purmerend
  - RAD
  - RecycleApp (don't forget the streetname option)
  - RD4
  - RWM
  - Reinis
  - ROVA
  - RMN
  - Schouwen-Duiveland
  - Sliedrecht
  - Spaarnelanden
  - SudwestFryslan
  - TwenteMilieu
  - Venray
  - Voorschoten
  - Waalre
  - Waardlanden
  - Westland
  - Woerden
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
  - pbd
  - duobak
  - restwagen
  - sortibak

### Postcode
Postcode is required and is your own postcode

### Streetnumber
Streetnumber is required and is your own street number

### Suffix
```yaml
suffix: a
```
Optional streetnumber suffix

### Streetname
```yaml
streetname: ?
```
Streetname is only required for Ophaalkalender.be and Limburg.NET

### Cityname
```yaml
cityname: ?
```
Cityname is only required for Limburg.NET

### Print all available waste fractions
```yaml
printwastetypes: 1
```
If you set this option the sensor will print a list of all possible waste fractions for your address and waste collector on every restart of your HA system. You can find this list in the persistent notifications.

### Upcoming sensor
```yaml
upcomingsensor: 1
```
If you activate this option you'll get 3 extra sensors (today, tomorrow and next upcoming) which are handy for automations.
The today sensor will display the fractions collected today.
The tomorrow sensor will display the fractions collected tomorrow.
The next upcoming sensor will display the date and fractions closest in the future.
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

### Day of week
```yaml
dayofweek: 1
```
This option adds the name of the day to the state of the sensor when the date is within 7 days. Default is 1.

### Day of week only
```yaml
dayofweekonly: 1
```
This option removes the date from the sensor if `dayofweek` is active. Default is 0.

### Always show day
```yaml
alwaysshowday: 1
```
This option removes the 7 day limit of `dayofweek`. Default is 0.

### Date object
```yaml
dateobject: 1
```
If you want the sensor state to be a date-time object. Default is 0 (state as string).

### Name
```yaml
name: 'your custom name'
```
If you want a custom name to be added to the sensor name. By default, no name is added. This is especially useful when you configure more than one sensor using this platform.

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

![Screenshot 2022-10-19 at 09 23 13](https://user-images.githubusercontent.com/7591990/196623891-bf169e71-9f65-4d32-bade-befecb1263d8.jpg)

### Use new built in icons
```yaml
builtiniconsnew: 1
```
Set this option if you want to use the new built in icons. Option `builtinicons` has to be 1.  Default is 0.
For now only these fractions are supported:
- gft
- gftgratis
- glas
- papier
- pmd
- pbd
- plastic
- zacht-plastic
- restafval
- kca
- textiel
- kerstbomen
- grofvuil
- tuinafval

![Screenshot 2022-10-19 at 09 21 50](https://user-images.githubusercontent.com/7591990/196623742-002840d9-6ecc-4100-9609-1b1f7302f86d.jpg)

### Disable the use of entity_picture
```yaml
disableicons: 1
```
If you want to assign MDI icons (in your customize section) to these sensors, you'll need to set this option to 1.

### Translation
```yaml
dutch: 1
```
If you want to display the names of the days in dutch. Default is 0.

### Update interval
```yaml
updateinterval: 12
```
If you want to adjust the update interval, you can set this option to the desired hours. Default is 12.

### Custom mapping of waste fractions
```yaml
custommapping:
  keukenafval: VET-goed
  fraction2: New name for fraction2
```
Some wastecollectors use the wrong fraction name and with this option you can override the default mapping. E.g. Meppel uses keukenafval for the fraction VET-goed, which by default gets mapped to GFT. Default is empty.

### Customer ID for Ximmio commercial address
```yaml
customerid: 123456
```
If you use have a commercial address (and use one of the Ximmio waste collectors), you need to input your Customer ID. Default is empty.

### Credits
Omrin API - @Jordi1990

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)
