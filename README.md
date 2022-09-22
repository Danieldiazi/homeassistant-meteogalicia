# homeassistant-meteogalicia
Meteo Galicia - Home Assistant Integration

![imagen](https://user-images.githubusercontent.com/3638478/191593829-b1ad8bec-b456-4023-9d4d-0e17796d27cc.png)

## Requisitos

Para instalar esta integración en Home Assistant necesitarás:

* una instalación de Home Assistant (HA),
* tener HACS en tu entorno de HA (ver <https://hacs.xyz/>)


## Instalación
Una vez cumplidos los objetivos anteriores, los pasos a seguir para la instalación de esta integración son los siguientes:

1. Añadir este repositorio (<https://github.com/Danieldiazi/homeassistant-meteogalicia>) a los repositorios personalizados de HACS,
   ![imagen](https://user-images.githubusercontent.com/3638478/191826846-7dc9b9b8-478e-45ed-9cc8-12553081a13a.png)

   ![imagen](https://user-images.githubusercontent.com/3638478/191592833-655e6ff8-c315-4d39-9e04-3812129336c4.png)

3. Instalar la integración mediante HACS,

   ![imagen](https://user-images.githubusercontent.com/3638478/191827262-2e0dc260-b275-409e-81df-b854e55bfe3d.png)

   
   ![imagen](https://user-images.githubusercontent.com/3638478/191827091-c60dff09-c632-497a-a291-38f75618ec07.png)
   
   ![imagen](https://user-images.githubusercontent.com/3638478/191827490-c2148e02-0f32-4624-8a49-89b53aa9636e.png)

   ![imagen](https://user-images.githubusercontent.com/3638478/191827562-dc11d755-c1d8-4040-a7dd-85de8a3212b6.png)


4. Configurarla mediante el fichero de configuración `configuration.yaml` (u otro que tengas configurado):

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

5. Aparecerá un mensaje de que hay que reiniciar

![imagen](https://user-images.githubusercontent.com/3638478/191827699-7bdc43b1-c18c-4bb8-81de-c03ecca969f7.png)

![imagen](https://user-images.githubusercontent.com/3638478/191827740-d495ed95-e02d-41de-93ca-04f7e13fc9b2.png)

6. Una vez reiniciado, esperar unos minutos a que aparezcan las nuevas entidades, con id: sensor.meteo_galicia_XXXX.
