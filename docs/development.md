# Pruebas y SonarQube Cloud

## Dependencias de CI

Los tests se ejecutan en Ubuntu 24.04 x86_64 con Python 3.14.2. Los archivos
`requirements_test.txt` y `requirements_build.txt` contienen las dependencias
directas; sus archivos `.lock` fijan también las indirectas y los hashes SHA-256.
El requisito de MeteoGalicia-API debe coincidir con `manifest.json`.

Para regenerar los locks, usa `uv` 0.12.19 y ejecuta desde la raíz:

```sh
uv pip compile requirements_test.txt --python-version 3.14.2 --python-platform x86_64-manylinux_2_39 --generate-hashes --only-binary :all: --no-binary mock-open,pyric -o requirements_test.lock
uv pip compile requirements_build.txt -c requirements_test.lock --python-version 3.14.2 --python-platform x86_64-manylinux_2_39 --generate-hashes --only-binary :all: -o requirements_build.lock
```

Revisa los cambios y ejecuta el workflow **Tests**. La instalación utiliza los locks;
`scripts/check_test_environment.py` comprueba después que las versiones instaladas
coinciden con los requisitos directos y el manifiesto de la integración. Un lock
desactualizado falla en CI. `pip check` comprueba las dependencias indirectas.

Se exige `--require-hashes` y se permiten únicamente wheels salvo dos dependencias
del entorno de pruebas de Home Assistant: `mock-open==1.4.0` y `PyRIC==0.1.6.3`.
PyPI solo publica sus distribuciones fuente. Se han revisado sus scripts de
instalación: utilizan setuptools para empaquetar los módulos. Sus archivos fuente
están fijados por hash; setuptools, wheel y sus dependencias también están fijados.
`--no-build-isolation` evita descargar herramientas de compilación sin bloquear.
Si se actualiza cualquiera de estas dos excepciones, revisa de nuevo su fuente y
comprueba si ya existe un wheel antes de conservar la excepción.

## Activar análisis con cobertura

El análisis automático de SonarQube Cloud lee `.sonarcloud.properties`, pero no
importa cobertura. El análisis desde GitHub Actions utiliza
`sonar-project.properties` y el `coverage.xml` generado por los tests.

Para activar este último, un administrador debe:

1. Preparar un token de SonarQube Cloud con permiso **Execute Analysis** sobre
   este proyecto y guardarlo de forma privada como secreto de Actions llamado
   `SONAR_TOKEN` en el repositorio. No lo guardes en archivos ni lo pegues en chats.
2. En el proyecto de SonarQube Cloud, ir a **Administration → Analysis Method** y
   desactivar **Automatic Analysis**; ambos métodos no pueden funcionar a la vez.
3. Ejecutar **Actions → Tests → Run workflow** sobre `main` y comprobar que
   **Publish coverage to SonarQube Cloud** se ejecuta y termina correctamente.

Mientras el secreto no esté disponible, CI muestra una advertencia explícita.
Los pull requests de forks no reciben secretos; sus tests siguen ejecutándose.
El token solo se expone a los pasos de configuración y análisis, no a la
instalación de dependencias ni a los tests.

Ambos archivos de configuración incluyen la integración, los workflows, los
scripts y los tests. No se excluyen workflows para ocultar incidencias de seguridad.
La excepción `NOSONAR(S7503)` de diagnósticos se limita a esa regla en la declaración:
Home Assistant exige que ese callback sea `async`, aunque lea datos en memoria.

Referencias: [análisis automático de SonarQube Cloud](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/automatic-analysis)
y [contrato de diagnósticos de Home Assistant](https://developers.home-assistant.io/docs/core/integration/diagnostics/).
