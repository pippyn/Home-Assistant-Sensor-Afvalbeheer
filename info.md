[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch and Belgium waste collectors using REST API. This sensor works with the following waste collectors: Blink, Cure, Suez, ACV, Twente Milieu, Hellendoorn, Cyclus, DAR, HVC Groep, Meerlanden, RMN (Reinigingsbedrijf Midden Nederland), Peel en Maas, Purmerend, Circulus-Berkel (Afvalvrij), Avalex, Venray, Den Haag, Berkelland, Alphen aan den Rijn, Waalre, ZRD, Spaarnelanden, SudwestFryslan, Montfoort, GAD, Cranendonck, ROVA, RD4, Limburg.NET, AfvalAlert, Ophaalkalender, DeAfvalApp, Alkmaar and Area Reiniging.

Cure users should switch to the waste collector MijnAfvalwijzer

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
