## Home Assisant sensor component for Afvalbeheer

Provides Home Assistant sensors for multiple Dutch waste collectors using REST API.
This sensor works with the following waste collectors: Blink, Cure, Cyclus, DAR, HVC Groep, Meerlanden, RMN (Reinigingsbedrijf Midden Nederland), Peel en Maas, Circulus-Berkel (Afvalvrij), Avalex, Venray, Den Haag, Berkelland, Alphen aan den Rijn, Waalre, ZRD, Spaarnelanden, Montfoort, GAD and Cranendonck.

![alt text](https://github.com/pippyn/Home-Assisant-Sensor-Cure-Afvalbeheer/blob/master/example.png)

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
      nameprefix: 1                    (optional)
      builtinicons: 0                  (optional)
      dutch: 0                         (optional)
```
For more information visit the repository
