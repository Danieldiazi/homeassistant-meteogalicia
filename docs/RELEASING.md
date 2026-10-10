# Publicar una versión

1. Si cambia algún archivo de `custom_components/meteogalicia`, aumenta `version`
   en `manifest.json` antes de fusionar el PR.
2. Mantén `MeteoGalicia-API` fijada a una versión ya disponible en PyPI y usa la
   misma versión en la integración de mareas, para evitar conflictos.
3. Publica una release con la versión del manifiesto, por ejemplo `v2026.10.1`,
   o utiliza la rama `publish/v2026.10.1`.

El PR comprueba el incremento de versión, la dependencia publicada y el ZIP de
HACS. La publicación vuelve a comprobar que la etiqueta coincide con el
manifiesto y que el archivo contiene la integración en la raíz, sin una carpeta
adicional ni archivos temporales. Un fallo impide adjuntar un ZIP incorrecto.

Puedes comprobar el paquete antes de publicar:

```sh
python -m unittest discover -s tests_release -v
python scripts/release.py --domain meteogalicia --tag v2026.10.1 --output homeassistant-meteogalicia.zip --verify-dependencies
```
