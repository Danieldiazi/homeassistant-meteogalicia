# homeassistant-meteogalicia
Meteo Galicia - Home Assistant Integration


## Requisitos

Para instalar esta integración en Home Assistant necesitarás:

* una instalación de Home Assistant (HA),
* tener HACS en tu entorno de HA (ver <https://hacs.xyz/>)


## Instalación
Una vez cumplidos los objetivos anteriores, los pasos a seguir para la instalación de esta integración son los siguientes:

1. Añadir este repositorio (<https://github.com/Danieldiazi/homeassistant-meteogalicia>) a los repositorios personalizados de HACS,
   ![imagen](https://user-images.githubusercontent.com/3638478/191592833-655e6ff8-c315-4d39-9e04-3812129336c4.png)

3. Instalar la integración mediante HACS, y
4. Configurarla mediante el fichero de configuración `configuration.yaml` (u otro que tengas configurado):

``` yaml
sensor:
  platform: meteogalicia
  id_concello: 32054
```

4. Esperar unos minutos a que aparezcan las nuevas entidades, con id: sensor.meteo_galicia_XXXX.
