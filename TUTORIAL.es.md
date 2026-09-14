# Una predicción correcta puede acabar junto al registro equivocado

Este experimento reproduce errores de empaquetado antes de una subida manual. Todos los genes, células, valores y registros son inventados. No se ejecuta ningún modelo, no se calcula una puntuación científica y no se accede a datos del concurso.

## Ejecuta el experimento

Desde esta carpeta, instala únicamente las dependencias del ejemplo y elige una carpeta de salida nueva:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
.venv/bin/python demo_synthetic.py --out /tmp/vec-demo-es
```

El ejemplo escribe un archivo AnnData de 8 células y 5 genes ficticios. Lo vuelve a abrir para comprobar que es un `.h5ad` legible. Ese tamaño y esos genes son educativos: **no constituyen una predicción válida para ningún tablero oficial**.

La herramienta crea una relación explícita entre un identificador de ejecución y sus archivos, registra sus huellas SHA-256 y después introduce errores controlados. En `summary.json` verás estos resultados observados:

| Caso | Resultado esperado | Qué demuestra |
|---|---|---|
| Paquete completo, almacenamiento previo declarado | `pass` | Las comprobaciones locales de empaquetado terminan correctamente |
| Almacenamiento previo desconocido | `incomplete` | No se supone que el equipo tiene cero archivos |
| Almacenamiento previo agotado | `fail` | Un paquete pequeño también puede exceder el límite total |
| Dos tipos de evidencia, fase de puntuación | `pass` | Se comprueba la fase elegida |
| Los mismos dos tipos, nominación final | `fail` | Falta el archivo del arnés requerido para la nominación |
| Evidencia etiquetada con otra ejecución | `fail` | Un identificador mezclado no pasa inadvertido |
| Predicción modificada, mismo tamaño y AnnData legible | `fail` | El tamaño del archivo no basta para identificar su contenido |

## El fallo que una comparación de tamaños no detecta

En `changed-prediction/`, el programa cambia un valor de la matriz dentro de HDF5. El archivo mantiene su tamaño y sigue abriéndose con AnnData. Aun así, su contenido ya no coincide con la predicción seleccionada al crear el manifiesto.

```bash
python3 vec_evidence.py audit /tmp/vec-demo-es/changed-prediction/manifest.json \
  --phase final --already-used-bytes 0
```

El código de salida es 1 y el informe indica un cambio de SHA-256. La corrección consiste en recuperar los archivos exactos de la ejecución seleccionada. Si realmente vas a presentar otra ejecución, conserva la anterior y prepara una carpeta y un manifiesto nuevos. Reescribir el manifiesto solo para ocultar un cambio elimina la utilidad de esta comprobación.

## El paquete que permite puntuar, pero todavía está incompleto para el premio

```bash
python3 vec_evidence.py audit /tmp/vec-demo-es/scoring-only/manifest.json \
  --phase scoring --already-used-bytes 0
python3 vec_evidence.py audit /tmp/vec-demo-es/scoring-only/manifest.json \
  --phase final --already-used-bytes 0
```

La primera comprobación pasa. La segunda falla porque falta `harness`. El archivo debe proceder de la misma ejecución; el programa no lo escribe por ti. Esta separación evita confundir un paquete que puede entrar en evaluación con uno completo para la nominación final.

## Qué conserva el manifiesto

El manifiesto contiene rutas relativas, tipos, identificadores de ejecución, tamaños y huellas. No copia el texto de los prompts ni de la trayectoria en el informe. No hace peticiones de red y no abre archivos que no hayas enumerado.

La etiqueta `run_id` es una declaración tuya. El programa detecta contradicciones y cambios, pero no puede demostrar que esa etiqueta sea cierta ni que la ejecución fuera autónoma. Tampoco evalúa el contenido de un prompt, la calidad científica o la licencia de los datos. Lee estas limitaciones antes de interpretar un resultado `pass`.

## Llevarlo a tu trabajo

Usa los pasos de [README](README.md) con tus archivos reales. Mantén el manifiesto original, comprueba de nuevo después de copiar el paquete a otra máquina y selecciona manualmente cada archivo en el portal. Nunca subas los ejemplos sintéticos de esta carpeta como una participación real.

Las reglas consultadas están enlazadas en README. La web puede cambiarlas: el informe muestra la fecha de la política aplicada. La comprobación local no sustituye una confirmación del organizador.

Las 29 pruebas de comportamiento también cubren entradas malformadas, incluidos tipos de evidencia que no son texto y JSON con UTF-8 dañado. Se ejecutan sin las dependencias de AnnData:

```bash
python3 -m unittest -v test_vec_evidence.py
```
