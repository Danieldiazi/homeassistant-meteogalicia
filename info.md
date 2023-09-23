[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz)
![GitHub Activity](https://img.shields.io/github/commit-activity/m/danieldiazi/homeassistant-meteogalicia?label=commits)
![GitHub Release](https://img.shields.io/github/v/release/danieldiazi/homeassistant-meteogalicia)

**town hall or city data -  configuration.yaml:**

```yaml
sensor:
  platform: meteogalicia
  id_concello: 32054
  scan_interval: 1800
```

Many sensors:

``` yaml
sensor:
  - platform: meteogalicia
    id_concello: 32054
    scan_interval: 1200
  - platform: meteogalicia
    id_concello: 15023
    scan_interval: 1800
```


**Configuration variables:**  
  
key | description  
:--- | :---  
**platform (Required)** | The platform name: "meteogalicia".  
**id_concello (Required)** | The ID of your town hall or city hall provided by Meteo Galicia.  
**scan_interval (Optional)** | Interval in seconds to poll new data from meteogalicia webservice. 
  
   
Updated info about MeteoGalicia services and "id_concello" values can be obtained in:  [https://meteogalicia.gal/datosred/infoweb/meteo/docs/rss/JSON_Pred_Concello_gl.pdf](https://meteogalicia.gal/datosred/infoweb/meteo/docs/rss/JSON_Pred_Concello_gl.pdf). 





**weather stations - configuration.yaml:**

```yaml
sensor:
  platform: meteogalicia
  id_estacion: 10124
  scan_interval: 1800
```

Many sensors:

``` yaml
sensor:
  - platform: meteogalicia
    id_estacion: 10124
    scan_interval: 1800
  - platform: meteogalicia
    id_estacion: 10124
    id_estacion_medida_diarios: BH_SUM_1.5m
    scan_interval: 1800

  - platform: meteogalicia
    id_estacion: 10124
    id_estacion_medida_ultimos_10_min: DV_AVG_10m
    scan_interval: 1800

```


**Configuration variables:**  
  
key | description  
:--- | :---  
**platform (Required)** | The platform name: "meteogalicia".  
**id_estacion (Required)** | The ID of the weather station provided by Meteo Galicia.  
**id_estacion_medida_diarios (Optional)** | Param id used as state value obtained from "datos diarios" service.
**id_estacion_medida_ultimos_10_min (Optional)** | Param id to use as state value from "ultimos 10min" service.
**scan_interval (Optional)** | Interval in seconds to poll new data from meteogalicia webservice.  Recommended.
  
   
Updated info about "id_estacion" values can be obtained in: https://servizos.meteogalicia.gal/mgrss/observacion/listaEstacionsMeteo.action. 
Updated info about "id_estacion_medida_diarios" or "id_estacion_medida_ultimos_10_min" values can be obtained in: [https://www.meteogalicia.gal/observacion/rede/parametrosIndex.action](https://www.meteogalicia.gal/observacion/rede/parametrosIndex.action) . Moreover, you can see this values on your own sensor as attributes.



