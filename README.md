[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz)
![GitHub Activity](https://img.shields.io/github/commit-activity/m/danieldiazi/homeassistant-meteogalicia?label=commits)
![GitHub Release](https://img.shields.io/github/v/release/danieldiazi/homeassistant-meteogalicia)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Danieldiazi_homeassistant-meteogalicia&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Danieldiazi_homeassistant-meteogalicia)

# homeassistant-meteogalicia
MeteoGalicia - Integración para Home Assistant 

Esta integración para [Home Assistant](https://www.home-assistant.io/) te permite obtener información meteorológica de aquellos ayuntamientos de Galicia que sean de tu interés. La información se obtiene de los servicios webs proporcionados por [MeteoGalicia](https://www.meteogalicia.gal/), organismo oficial que tiene entre otros objetivos la predicción meteorológica de Galicia.

![imagen](https://user-images.githubusercontent.com/3638478/191593829-b1ad8bec-b456-4023-9d4d-0e17796d27cc.png)
![imagen](https://github.com/Danieldiazi/homeassistant-meteogalicia/assets/3638478/6df78b47-a9f4-4b31-8ed3-1e2bb3e3d0a3)
![imagen](https://github.com/Danieldiazi/homeassistant-meteogalicia/assets/3638478/37db37e6-52ac-4152-926f-95b5b2c9e40c)

## Características

Proporciona sensores y una entidad meteorológica:

- Para un ayuntamiento dado
  - Entidad `weather` con temperatura, sensación térmica y estado del cielo observados, además de la previsión diaria disponible (temperaturas máxima y mínima, probabilidad de lluvia e índice UV).
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
  - Una entidad independiente por cada medida que ofrece la estación: temperatura,
    humedad, presión, lluvia, radiación, velocidad y dirección del viento, entre otras.
  - Medidas de los últimos 10 minutos y datos diarios, con unidad, clase de dispositivo
    y clase de estado cuando Home Assistant dispone de una equivalencia nativa.
  - Las entidades-resumen anteriores se conservan para no romper automatizaciones ni
    perder la continuidad del historial.
  
  


## Requisitos

Para instalar esta integración en Home Assistant necesitarás:

* una instalación de Home Assistant (ver <https://www.home-assistant.io/>)
* tener HACS en tu entorno de Home Assistant (ver <https://hacs.xyz/>)


## Instalación
Una vez cumplidos los objetivos anteriores, los pasos a seguir para la instalación de esta integración son los siguientes:

1. Pulsa en [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=danieldiazi&repository=homeassistant-meteogalicia&category=integration)
  
2. Instalar la integración mediante HACS. [Más info](docs/HACS_add_integration.md)

3. Reiniciar Home Assistant.

4. Configuracion por interfaz (UI):

   - Ve a Settings > Devices & Services > Add Integration.
   - Busca "MeteoGalicia" y elige el tipo de datos:
     - Forecast (concello): usa `id_concello`.
     - Station (estacion): usa `id_estacion` y opcionalmente las medidas.
   - Completa el formulario y guarda. La integración comprueba el identificador con
     MeteoGalicia antes de crear la entrada y utiliza el nombre real del concello o
     de la estación.
   - (Opcional) En la pantalla de opciones puedes ajustar `scan_interval` en segundos;
     el nuevo intervalo se aplica automáticamente al guardar, sin reiniciar Home Assistant.

5. Reinicia Home Assistant y espera unos minutos a que aparezcan las nuevas entidades.

### Migración automática desde YAML

Las configuraciones antiguas con `platform: meteogalicia` se importan automáticamente como entradas de configuración al actualizar la integración y reiniciar Home Assistant.

- Se crea una entrada por cada bloque YAML.
- Se conservan `id_concello`, `id_estacion`, la medida seleccionada y el `scan_interval` exacto.
- Se mantienen los `unique_id` de las entidades para conservar sus identificadores e historial.
- Si la entrada ya existe, no se crea un duplicado.
- En **Ajustes → Sistema → Reparaciones** aparece un aviso con el bloque correspondiente que ya puedes eliminar de `configuration.yaml`.
- El aviso desaparece después de retirar el bloque YAML y reiniciar Home Assistant.

No añadas nuevas configuraciones YAML: utiliza **Ajustes → Dispositivos y servicios → Añadir integración → MeteoGalicia**.

### Update interval (scan_interval)

- El `scan_interval` se aplica por cada entrada de configuración, no por sensor individual.
- Todas las entidades que cuelgan del mismo coordinador comparten el mismo `update_interval`.
- Puedes tener varias entradas del mismo tipo y cada una puede usar un intervalo distinto.
- Si MeteoGalicia devuelve temporalmente una respuesta vacía, se conservan los últimos
  datos válidos y la actualización se marca como fallida hasta que el servicio se recupere.

## Diagnostics

La integración soporta diagnósticos desde la UI para entradas creadas por config flow.
Incluyen el tipo de entrada, sus entidades y el estado de cada coordinador: último éxito,
latencia, intervalo efectivo, disponibilidad y último error. Los payloads completos de la
API no se incluyen.

## Autenticacion

MeteoGalicia no requiere autenticacion ni credenciales.

## Entidades

- Concello (forecast + observation):
  - Entidad meteorológica (`weather`) con previsión diaria
  - Temperatura actual
  - Max/Min hoy y manana
  - Probabilidad de lluvia hoy y manana
- Estacion:
  - Una entidad por medida diaria disponible
  - Una entidad por medida de los últimos 10 minutos disponible
  - Sensores resumen heredados para compatibilidad


## FAQ

###### ClientConnectorError
Aparece el mensaje "[custom_components.meteogalicia.sensor] [ClientConnectorError] Cannot connect to host servizos.meteogalicia.gal:443 ssl:default [Try again]* -> Lo más probable es que en ese momento no tuvieses acceso a internet desde tu Home Assistant.¡

###### TimeoutError
Si aparece el mensaje *Couldn't update sensor (TimeoutError)* o *Still no update available (TimeoutError)* en este caso es un problema con el servicio web de meteogalicia, en ese momento puntual no habrá podido servir la petición. En función del valor de "scan_interval" tocará esperar ese tiempo para que vuelva a intentarlo.

###### Currently unable to download asked data from MeteoGalicia: Or station id: XXXX doesn't exists or there are a possible API connection problem
En este caso hay dos opciones
- Se ha introducido un identificador de estación no existente. Deberás revisar la lista de id's de estaciones.
- Se ha intentado conectar al servicio web de meteogalicia y ha devuelto contenido vacío. Este caso es el de los sensores de las estaciones meteorológicas y el de datos diarios, en el que de madrugada, a partir de las 00:00 deja de funcionar unas horas (varía en función de horario de verano o invierno). Debes esperar.
