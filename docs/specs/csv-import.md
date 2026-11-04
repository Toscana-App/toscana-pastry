# Importación de datos con CSV (Next.js + Python)

**Recomendación:** no usar una plataforma de importación, sino armar el flujo con FastAPI, Pydantic y una tabla de staging en la base de datos. Es simple y permite controlar la validación. Lo más importante es que el backend sea la fuente de verdad.

> **Supuestos:** el backend usa FastAPI y "buffer" significa guardar los datos temporalmente antes de confirmarlos.

## Stack

- **Plantilla:** un endpoint `GET /imports/template`, que genere el CSV a partir del mismo esquema que se usa para validar. Así la plantilla y la validación no se desincronizan.
- **Carga en Next.js:** `react-dropzone` para adjuntar el archivo y Papa Parse para mostrar una vista previa.
- **Lectura en Python:** `csv.DictReader` para archivos chicos o Polars para archivos grandes o procesamiento pesado. Con FastAPI, recibir el archivo con `UploadFile`.
- **Validación:** Pydantic, fila por fila, devolviendo los errores con su número de fila y columna.
- **Buffer:** una tabla de staging en PostgreSQL o en la base que ya se use.

## Flujo

1. El usuario descarga la plantilla y la completa.
2. Sube el CSV y el backend crea un `import_id`.
3. El backend valida los datos y guarda las filas en staging, con su estado y sus errores.
4. El usuario revisa el resultado y confirma.
5. Una transacción pasa las filas válidas a las tablas finales.

## Tabla mínima

```sql
import_rows (
  id,
  import_id,
  row_number,
  data JSONB,
  status,
  errors JSONB,
  created_at
)
```

## Qué evitar o tener en cuenta

- **Memoria o `BytesIO`:** no sirven como buffer entre pasos porque los datos se pierden al reiniciar y fallan con varias instancias.
- **Redis:** sirve solo si el buffer es temporal, con vencimiento, y no se necesita consultarlo mucho.
- **Reglas de archivo:** limitar el tamaño y controlar el encoding, ya que Excel suele usar UTF-8 con BOM o Latin-1. También puede usar `;` como separador, algo común con la configuración regional de Argentina.
- **Archivos grandes:** a partir de unas 50.000 a 100.000 filas, procesarlos en segundo plano con Celery o RQ. Como referencia, si el proceso supera el timeout de la request, ya conviene hacerlo.

## Opcionales

- **`react-spreadsheet-import`:** sumarlo si el usuario necesita mapear columnas y corregir errores en una interfaz tipo planilla.
- **Flatfile u OneSchema:** se justifican solo si se reciben muchos formatos distintos de clientes externos.
