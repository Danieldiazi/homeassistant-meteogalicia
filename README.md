[![HACS Supported](https://img.shields.io/badge/HACS-Supported-green.svg)](https://github.com/custom-components/hacs)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![GitHub Activity](https://img.shields.io/github/commit-activity/m/danieldiazi/homeassistant-meteogalicia?label=commits)
![GitHub Release](https://img.shields.io/github/v/release/danieldiazi/homeassistant-meteogalicia)

# homeassistant-meteogalicia
MeteoGalicia - Home Assistant Integration

Esta integración para Home Assistant te permite obtener información meteorológica de aquellos ayuntamientos de Galicia que sean de tu interés. La información se obtiene de los servicios webs proporcionados por [MeteoGalicia](https://www.meteogalicia.gal/), organismo oficial que tiene entre otros objetivos la predicción meteorológica de Galicia.

![imagen](https://user-images.githubusercontent.com/3638478/191593829-b1ad8bec-b456-4023-9d4d-0e17796d27cc.png)

## Requisitos

Para instalar esta integración en Home Assistant necesitarás:

* una instalación de Home Assistant (HA),
* tener HACS en tu entorno de HA (ver <https://hacs.xyz/>)


## Instalación
Una vez cumplidos los objetivos anteriores, los pasos a seguir para la instalación de esta integración son los siguientes:

1. Añadir este repositorio (<https://github.com/Danieldiazi/homeassistant-meteogalicia>) a los repositorios personalizados de HACS. [Más info](docs/HACS_add_repo.md) 
  

3. Instalar la integración mediante HACS. [Más info](docs/HACS_add_integration.md)

4. Reiniciar HA.

5. Configurarla mediante el fichero de configuración `configuration.yaml` (u otro que uses):

``` yaml
sensor:
  platform: meteogalicia
  id_concello: 32054 
```

Puedes poner más de un sensor, por ejemplo:

``` yaml
sensor:
  - platform: meteogalicia
    id_concello: 32054
  - platform: meteogalicia
    id_concello: 15023
```


La lista de id's se pueden encontrar en el enlace [info.md](info.md)

5. Reiniciar para que recarge la configuración y espera unos minutos a que aparezcan las nuevas entidades, con id: sensor.meteo_galicia_XXXX.


## FAQ

###### ClientConnectorError
Aparece el mensaje "[custom_components.meteogalicia.sensor] [ClientConnectorError] Cannot connect to host servizos.meteogalicia.gal:443 ssl:default [Try again]* -> Lo más probable es que en ese momento no tuvieses acceso a internet desde tu HA.



###### TimeoutError
Si aparece el mensaje *Couldn't update sensor (TimeoutError)* o *Still no update available (TimeoutError)* en este caso es un problema con el servicio web de meteogalicia, en ese momento puntual no habrá podido servir la petición.
