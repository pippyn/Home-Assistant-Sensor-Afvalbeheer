[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch waste collectors using REST API.
This sensor works with the following waste collectors: Blink, Suez, Cyclus, DAR, HVC Groep, Meerlanden, RMN (Reinigingsbedrijf Midden Nederland), Peel en Maas, Purmerend, Circulus-Berkel (Afvalvrij), Avalex, Venray, Den Haag, Berkelland, Alphen aan den Rijn, Waalre, ZRD, Spaarnelanden, Montfoort, GAD, Cranendonck and Alkmaar.


**Starting from version 3.0.0 this sensor now also supports MijnAfvalwijzer and Afvalstoffendienstkalender**

Cure users should switch to the waste collector MijnAfvalwijzer

Meerlanden users should switch to the waste collector Ximmio


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
