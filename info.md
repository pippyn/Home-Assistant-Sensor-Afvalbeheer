[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)
## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch and Belgium waste collectors using REST API. 
This sensor works with the following waste collectors:
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
  - DeFryskeMarren
  - DeAfvalApp
  - DenHaag
  - Drimmelen
  - GAD
  - Groningen
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
  - Saver
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

![alt text](https://raw.githubusercontent.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/master/example.png)

### Example config:

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
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pippyn)

[For more information visit the repository](https://github.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/)
