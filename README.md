[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz)
![GitHub Activity](https://img.shields.io/github/commit-activity/m/danieldiazi/homeassistant-meteogalicia?label=commits)
![GitHub Release](https://img.shields.io/github/v/release/danieldiazi/homeassistant-meteogalicia)

# homeassistant-meteogalicia
MeteoGalicia - Home Assistant Integration

Esta integración para [Home Assistant](https://www.home-assistant.io/) te permite obtener información meteorológica de aquellos ayuntamientos de Galicia que sean de tu interés. La información se obtiene de los servicios webs proporcionados por [MeteoGalicia](https://www.meteogalicia.gal/), organismo oficial que tiene entre otros objetivos la predicción meteorológica de Galicia.

![imagen](https://user-images.githubusercontent.com/3638478/191593829-b1ad8bec-b456-4023-9d4d-0e17796d27cc.png)

## Características

Proporciona los siguientes sensores:

- Para un ayuntamiento dado
  - Observación meteorológica:
    - Temperatura actual.
  - Pronósticos:
    - Para el día actual
      - Temperatura máxima
      - Temperatura mínima
      - Probabilidad de lluvia
    - Para el día siguiente
      - Temperatura máxima
      - Temperatura mínima
      - Probabilidad de lluvia
  - Para una estación meteorológica dada
    -   Observación meteorológica
        -  Ultimos datos diarios (10-minutales).
        -  Datos diarios.
  
  


## Requisitos

Para instalar esta integración en Home Assistant necesitarás:

* una instalación de Home Assistant (ver <https://www.home-assistant.io/>)
* tener HACS en tu entorno de Home Assistant (ver <https://hacs.xyz/>)


## Instalación
Una vez cumplidos los objetivos anteriores, los pasos a seguir para la instalación de esta integración son los siguientes:

1. Pulsa en [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=danieldiazi&repository=homeassistant-meteogalicia&category=integration)
  
2. Instalar la integración mediante HACS. [Más info](docs/HACS_add_integration.md)

3. Reiniciar Home Assistant.

4. Configurarla mediante el fichero de configuración `configuration.yaml` (u otro que uses):

 Si quieres añadir la información para un ayuntamiento dado:
``` yaml
sensor:
  platform: meteogalicia
  id_concello: 32054
  scan_interval: 1200

```

Puedes poner más de un sensor, por ejemplo:

``` yaml
sensor:
  - platform: meteogalicia
    id_concello: 32054
    scan_interval: 1200
  - platform: meteogalicia
    id_concello: 15023
    scan_interval: 1800
```


- La lista de id's para rellenar el parámetro "id_concello" se pueden encontrar en el enlace [info.md](info.md)
- Con el parámetro opcional "scan_interval" indicas cada cuanto tiempo se conecta a meteogalicia para obtener la información. El valor es en segundos, por tanto, si pones 1200  hará el chequeo cada 20 minutos. Es recomendable usarlo.

En el caso de que quieras añadir información de estaciones meteorológicas:
``` yaml
sensor:
  platform: meteogalicia
  id_estacion: 10124
  scan_interval: 1800
```
Este ejemplo creará dos sensores,  uno para los últimos datos diarios y otro para los 10-minutales. En los atributos de cada sensor aparecerán todos los valores de las medidas que proporciona esa estación, si quieres que uno de esos valores sea el valor del estado del sensor creado, deberás usar el parámetro "id_estacion_medida_diarios" si la fuente de datos es de datos diarios o "id_estacion_medida_ultimos_10_min" si la fuente de datos diarios es la de los ultimos 10-minutales.

- La lista de id's se pueden encontrar en el enlace [info.md](info.md)
- Con el parámetro opcional "scan_interval" indicas cada cuanto tiempo se conecta a meteogalicia para obtener la información. El valor es en segundos, por tanto, si pones 1200  hará el chequeo cada 20 minutos. Es recomendable usarlo.
  
5. Reiniciar para que recarge la configuración y espera unos minutos a que aparezcan las nuevas entidades, con id: sensor.meteogalicia_XXXX.


## FAQ

###### ClientConnectorError
Aparece el mensaje "[custom_components.meteogalicia.sensor] [ClientConnectorError] Cannot connect to host servizos.meteogalicia.gal:443 ssl:default [Try again]* -> Lo más probable es que en ese momento no tuvieses acceso a internet desde tu Home Assistant.



###### TimeoutError
Si aparece el mensaje *Couldn't update sensor (TimeoutError)* o *Still no update available (TimeoutError)* en este caso es un problema con el servicio web de meteogalicia, en ese momento puntual no habrá podido servir la petición.
