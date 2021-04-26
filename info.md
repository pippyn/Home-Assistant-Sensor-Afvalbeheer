[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch and Belgium waste collectors using REST API. 
This sensor works with the following waste collectors:
  - ACV
  - Afvalstoffendienstkalender
  - AfvalAlert
  - Alkmaar
  - Almere
  - AlphenAanDenRijn
  - AreaReiniging
  - Avalex
  - Avri
  - BAR
  - Berkelland
  - Blink
  - Circulus-Berkel
  - Cranendonck
  - Cure (use MijnAfvalwijzer)
  - Cyclus
  - DAR
  - DeAfvalApp
  - DenHaag
  - GAD
  - Hellendoorn
  - HVC
  - Limburg.NET (don't forget the streetname and cityname option)
  - Meerlanden
  - Meppel
  - Middelburg-Vlissingen
  - MijnAfvalwijzer
  - Montfoort
  - Omrin
  - PeelEnMaas
  - Purmerend
  - RAD
  - RecycleApp (don't forget the streetname option)
  - RD4
  - Reinis
  - ROVA
  - RMN
  - Schouwen-Duiveland
  - Spaarnelanden
  - SudwestFryslan
  - Twente Milieu
  - Venray
  - Waalre
  - Waardlanden
  - ZRD

![alt text](https://raw.githubusercontent.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/master/example.png)

### Example config:

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
      name: ""                         (optional)
      nameprefix: 1                    (optional)
      builtinicons: 0                  (optional)
      dutch: 0                         (optional)
```
[For more information visit the repository](https://github.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/)

[![Buy me a coffee][buymeacoffee-shield]][buymeacoffee]


[buymeacoffee-shield]: https://www.buymeacoffee.com/assets/img/guidelines/download-assets-sm-2.svg
[buymeacoffee]: https://www.buymeacoffee.com/pippyn
