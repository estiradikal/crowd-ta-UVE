# INFORME COMPLETO: Panel de Evaluación de Usabilidad

## Índice

1. [Descripción del Proyecto](#1-descripción-del-proyecto)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Estructura del Proyecto](#3-estructura-del-proyecto)
4. [Modelos de Base de Datos](#4-modelos-de-base-de-datos)
5. [Flujo de la Aplicación](#5-flujo-de-la-aplicación)
6. [Funcionalidades Nuevas](#6-funcionalidades-nuevas)
7. [URLs del Sistema](#7-urls-del-sistema)
8. [Cómo Ejecutar](#8-cómo-ejecutar)
9. [Accesos](#9-accesos)
10. [Exportación a Excel](#10-exportación-a-excel)
11. [Archivos Creados/Modificados](#11-archivos-creadostestmodificados)

---

## 1. Descripción del Proyecto

Plataforma web de **Crowdsourcing para Tests de Usabilidad** compuesta por dos módulos principales:

### Módulo 1: Workers (Original)
- Los micro-workers realizan tareas en plataformas como EDX
- El sistema graba su pantalla, audio y cámara usando WebRTC
- Los videos se guardan en el servidor local

### Módulo 2: Evaluadores (NUEVO)
- Los evaluadores (staff Django) visualizan los videos grabados
- Anotan problemas de usabilidad usando una metodología estandarizada
- El sistema genera reportes en Excel con las anotaciones

---

## 2. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Django 3.0.8 (Python 3.13) |
| Frontend | Django Templates + Bootstrap 4 + jQuery |
| Base de datos | SQLite (`db.sqlite3`) |
| Grabación de video | Web MediaRecorder API (WebM) |
| Exportación | openpyxl (generación de Excel) |
| CSS | Bootstrap 4 CDN + CSS custom |
| JS | jQuery 3.5.1, jQuery UI, Bootstrap 4 JS |

---

## 3. Estructura del Proyecto

```
crowd-ta-UVE/
├── manage.py                              # Entry point de Django
├── requirements.txt                       # Dependencias Python
├── db.sqlite3                             # Base de datos SQLite
│
├── ta_crowdsource/                        # Configuración del proyecto
│   ├── settings.py                        # Configuración general
│   ├── urls.py                            # URLs raíz
│   ├── wsgi.py / asgi.py
│
├── usabilityTest/                         # App principal
│   ├── models.py                          # 13 modelos de BD
│   ├── views.py                           # Vistas originales (workers)
│   ├── urls.py                            # URLs originales
│   ├── forms.py                           # Formulario de registro
│   ├── admin.py                           # Registro en admin Django
│   │
│   ├── evaluation_views.py                # ★ NUEVO: Vistas del panel de evaluación
│   ├── evaluation_urls.py                 # ★ NUEVO: URLs del panel
│   │
│   ├── templates/
│   │   ├── main_templates/                # Templates originales (workers)
│   │   │   ├── base.html
│   │   │   ├── instructions.html
│   │   │   ├── user_registration.html
│   │   │   ├── microtasks.html
│   │   │   ├── recordmedia.html
│   │   │   └── payment.html
│   │   │
│   │   ├── evaluation/                    # ★ NUEVO: Templates del panel
│   │   │   ├── base_eval.html
│   │   │   ├── lista_videos.html
│   │   │   └── evaluar_video.html
│   │   │
│   │   └── 400.html, 403.html, 404.html, 500.html
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── base.css
│   │   │   ├── main.css
│   │   │   ├── stepper.css
│   │   │   └── eval_panel.css            # ★ NUEVO: CSS del panel
│   │   │
│   │   ├── js/
│   │   │   ├── mediarecoder.js
│   │   │   ├── soundmeter.js
│   │   │   ├── positiontracker.js
│   │   │   ├── tasksinfomanager.js
│   │   │   └── payment.js
│   │   │
│   │   └── img/
│   │
│   ├── uploads/                           # Videos subidos por workers
│   │   ├── mw-729286ff.../
│   │   │   ├── 1/2026-08-20/*.webm
│   │   │   └── 2/2026-08-20/*.webm
│   │   └── mw-7f5e5454.../
│   │       ├── 1/2026-08-20/*.webm
│   │       └── 2/2026-08-20/*.webm
│   │
│   └── migrations/
│       ├── 0001_initial.py
│       ├── 0002_...py
│       ├── 0003_...py
│       ├── 0004_...py
│       ├── 0005_evaluation_panel_models.py    # ★ NUEVO
│       └── 0006_populate_catalogs.py          # ★ NUEVO
│
├── Informe/                               # Documento LaTeX
└── venv/                                  # Entorno virtual Python
```

---

## 4. Modelos de Base de Datos

### 4.1 Modelos Originales (7)

#### SubjectProfile
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| payment_id | CharField(128) | Sí | ID de pago (hash SHA-256) |
| workerId | CharField(32) | No | ID del worker |
| campId | CharField(32) | No | ID de campaña |
| groupId | CharField(32) | No | ID de grupo |
| age | IntegerField | No | Edad |
| gender | CharField(32) | No | Género |
| birth_country | CountryField | No | País de nacimiento |
| residence_country | CountryField | No | País de residencia |
| mother_tongue | CharField(32) | No | Lengua materna |
| Do_you_speak_English | CharField(32) | No | Habla inglés |
| participated_before | CharField(32) | No | Participó antes |
| knowledge_on_usability | CharField(32) | No | Conocimiento en usabilidad |
| test_status | CharField(32) | No | Estado del test |

#### TaskInfo
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| id | AutoField | Sí | ID autoincremental |
| task_id | CharField(64) | No | ID de la tarea |
| task_ans | CharField(1024) | No | Respuesta del worker |
| test_id | CharField(128) | No | ID del test |

#### ClickInfo
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| id | AutoField | Sí | ID autoincremental |
| test_id | CharField(128) | No | ID del test |
| task_id | CharField(32) | No | ID de la tarea |
| click_info | TextField | No | Información de clicks |

#### TasksDescription
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| task_id | CharField(16) | Sí | ID de la tarea |
| task_description | TextField | No | Descripción de la tarea |
| task_valid_question | TextField | No | Pregunta de validación |
| valid_ans_options | CharField(128) | No | Opciones de respuesta |
| answer | CharField(128) | No | Respuesta correcta |

#### TaskStatus
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| subject_id | CharField(128) | Sí | ID del sujeto |
| task_1_valid_question | CharField(32) | No | Resultado tarea 1 |
| task_1_score | IntegerField | No | Puntuación tarea 1 |
| task_1_time | IntegerField | No | Tiempo tarea 1 |
| task_2_valid_question | CharField(32) | No | Resultado tarea 2 |
| task_2_score | IntegerField | No | Puntuación tarea 2 |
| task_2_time | IntegerField | No | Tiempo tarea 2 |
| test_result | CharField(32) | No | Resultado del test |
| test_rating | CharField(32) | No | Calificación del test |

#### Test_Input
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| campId | CharField(64) | Sí | ID de campaña |
| secret_key | CharField(100) | No | Clave secreta |
| application_url | CharField(100) | No | URL de la aplicación |

#### Approved_Testers
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| workerId | CharField(128) | Sí | ID del worker |
| status | CharField(32) | No | Estado (pending/approved) |

---

### 4.2 Modelos Nuevos - Catálogos (4)

#### EventCode (14 registros fijos)
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| code | CharField(16) | Sí | Código del indicador |
| short_description | CharField(128) | No | Nombre corto |
| definition | TextField | No | Definición completa |

**Registros:**
| Código | Nombre | Definición |
|---|---|---|
| ACT | wrong action | Acción que no pertenece a la secuencia correcta |
| DISC | discontinues action | El usuario apunta a una función pero no la ejecuta |
| EXE | execution problem | Acción ejecutada incorrectamente |
| REP | repeated action | Acción repetida con el mismo efecto |
| CORR | corrective action | Acción corregida con una subsiguiente |
| STOP | task stopped | Empieza nueva tarea sin terminar la actual |
| GOAL | wrong goal | Formula un objetivo que no se puede lograr |
| PUZZ | puzzled | No sabe cómo realizar la tarea |
| RAND | random actions | Acciones elegidas aleatoriamente |
| SEARCH | searches for function | No puede localizar una función específica |
| DIFF | execution difficulty | Dificultad física para ejecutar |
| DSF | doubt/surprise/frustration | No seguro si la acción fue correcta |
| REC | recognition of error | Reconoce un error anterior |
| QUIT | quits task | Reconoce que no terminó la tarea |

#### TaskContext (8 registros fijos)
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| name | CharField(64) | Sí | Nombre del momento |
| description | TextField | No | Descripción |
| example | TextField | No | Ejemplo |
| is_optional | BooleanField | No | Es opcional |

**Registros:**
| Nombre | Opcional |
|---|---|
| Qualification | Sí |
| Instructions | No |
| Demographic questionnaire | Sí |
| Training | No |
| Main task | No |
| Final questionnaire | Sí |
| Payment | No |
| Help/Support/Feedback | No |

#### SeverityLevel (3 registros fijos)
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| name | CharField(32) | Sí | Nombre del nivel |
| slowed_down | CharField(256) | No | Impacto en velocidad |
| understanding | CharField(256) | No | Impacto en comprensión |
| frustration | CharField(256) | No | Impacto en frustración |

**Registros:**
| Nivel | Ralentización | Comprensión | Frustración |
|---|---|---|---|
| Critical | Obstaculizado | No entiende cómo usar la info | — |
| Serious | Retrasado varios segundos | No entiende una funcionalidad | Claramente molesto |
| Cosmetic | Retrasado unos segundos | Hace acciones sin explicar por qué | — |

#### ProblemType (4 registros fijos)
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| name | CharField(32) | Sí | Nombre del tipo |
| definition | TextField | No | Definición |
| example | TextField | No | Ejemplo |

**Registros:**
| Tipo | Definición |
|---|---|
| Navigation | Problemas para navegar entre páginas |
| Layout | Dificultades con elementos web, display, visibilidad |
| Content | Información innecesaria, ausente o incomprensible |
| Functionality | Ausencia de funciones o problemas con funcionalidad |

---

### 4.3 Modelos Nuevos - Evaluación (3)

#### Evaluacion
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| id | AutoField | Sí | ID autoincremental |
| video_id | CharField(256) | No | Nombre del archivo de video |
| payment_id | CharField(256) | No | ID del worker |
| task_id | CharField(32) | No | Número de tarea |
| evaluador | ForeignKey(User) | No | Usuario evaluador |
| fecha_inicio | DateTimeField | No | Fecha de inicio |
| fecha_fin | DateTimeField | No | Fecha de finalización |
| completada | BooleanField | No | Está completada |
| observaciones_generales | TextField | No | Notas generales |

**Propiedades:**
- `total_anotaciones`: Cuenta de anotaciones
- `total_problemas`: Cuenta de problemas
- `severidad_counts`: Conteo por severidad

#### Anotacion
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| id | AutoField | Sí | ID autoincremental |
| evaluacion | ForeignKey(Evaluacion) | No | Evaluación padre |
| start_time | CharField(16) | No | Hora inicio (MM:SS) |
| finish_time | CharField(16) | No | Hora fin (MM:SS) |
| indicador | ForeignKey(EventCode) | No | Código del indicador |
| contexto | ForeignKey(TaskContext) | No | Momento de la tarea |
| problema | TextField | No | Descripción del problema |
| comentarios | TextField | No | Comentarios adicionales |
| fecha_creacion | DateTimeField | No | Fecha de creación |

#### ProblemaIdentificado
| Campo | Tipo | PK | Descripción |
|---|---|---|---|
| id | AutoField | Sí | ID autoincremental |
| evaluacion | ForeignKey(Evaluacion) | No | Evaluación padre |
| descripcion | TextField | No | Descripción del problema |
| severidad | ForeignKey(SeverityLevel) | No | Nivel de severidad |
| tipo | ForeignKey(ProblemType) | No | Tipo de problema |
| comentarios | TextField | No | Comentarios adicionales |
| fecha_creacion | DateTimeField | No | Fecha de creación |

---

## 5. Flujo de la Aplicación

### 5.1 Flujo del Worker (Original)

```
1. /index/
   → Genera IDs (workerId, campId, groupId)
   → Genera payment_id con SHA-256
   → Muestra instrucciones (iframe Google Docs)

2. /registration/
   → Formulario crispy (age, gender, país, idioma)

3. /tasks/
   → Video entrenamiento (YouTube)
   → Botón "Continue"

4. /test/<task_id>
   → PANTALLA PRINCIPAL:
     ├── Panel izquierdo: Stepper de tareas + cámara
     ├── Botón "Start Task" → Screen share + mic + cámara
     ├── Grabación en tiempo real (MediaRecorder API)
     ├── Medición de silencio (SoundMeter)
     ├── Tracking de clicks (positiontracker.js)
     ├── Pregunta de validación con autocomplete (jQuery UI)
     └── Subir video al terminar (AJAX → /upload/)

5. /payId/
   → Muestra Payment ID
   → Crea registro en Approved_Testers
```

### 5.2 Flujo del Evaluador (NUEVO)

```
1. /evaluacion/
   → Lista de videos disponibles
   ├── Estadísticas: Total, Evaluados, Pendientes
   ├── Filtros: Todos, Pendientes, En Progreso, Completadas
   ├── Búsqueda por Worker ID
   └── Click en "Evaluar"

2. /evaluacion/<payment_id>/<task_id>/
   → EVALUACIÓN:
     ├── VIDEO PLAYER (lado izquierdo)
     │   ├── Reproducir/pausar video
     │   ├── Selector de múltiples videos
     │   ├── Botón "Marcar tiempo" (captura timestamp actual)
     │   └── Jump-to-time desde anotaciones
     │
     ├── ANOTACIONES (abajo del video)
     │   ├── Formulario: hora inicio, hora fin, indicador, momento, problema, comentarios
     │   ├── Tabla con todas las anotaciones
     │   └── Eliminar anotaciones
     │
     ├── RESUMEN (columna derecha)
     │   ├── Contadores: anotaciones, problemas, severidad
     │   └── Estado de la evaluación
     │
     ├── PROBLEMAS (columna derecha)
     │   ├── Formulario: descripción, severidad, tipo, comentarios
     │   └── Lista de problemas identificados
     │
     ├── COMPLETAR
     │   ├── Observaciones generales
     │   └── Botón "Marcar como Completada"
     │
     └── DESCARGAR EXCEL (aparece al completar)
         └── Genera archivo .xlsx con 7 hojas

3. /evaluacion/<id>/exportar/
   → Descarga Excel
```

---

### 5.3 Diagrama de Flujo de Datos

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     WORKER      │     │     DJANGO      │     │   EVALUADOR     │
│                 │     │     SERVER      │     │                 │
│ 1. Graba video  │────→│                 │     │                 │
│    (WebM)       │     │ Guarda en:      │     │                 │
│                 │     │ /uploads/       │     │                 │
│ 2. Sube video   │────→│ {payment_id}/   │     │                 │
│    AJAX POST    │     │ {task_id}/      │     │                 │
│                 │     │ {fecha}/        │     │                 │
│                 │     │ *.webm          │     │                 │
│                 │     │                 │     │ 3. Ve lista     │
│                 │     │                 │←────│    de videos    │
│                 │     │                 │     │                 │
│                 │     │                 │     │ 4. Click        │
│                 │     │ Sirve video     │←────│    "Evaluar"    │
│                 │     │ via HTML5       │     │                 │
│                 │     │ <video> tag     │────→│ 5. Ve video     │
│                 │     │                 │     │    player       │
│                 │     │                 │     │                 │
│                 │     │                 │←────│ 6. Agrega       │
│                 │     │ Guarda en BD    │────→│    anotaciones  │
│                 │     │ Anotacion/      │     │                 │
│                 │     │ Problema        │     │ 7. Agrega       │
│                 │     │                 │←────│    problemas    │
│                 │     │                 │     │                 │
│                 │     │                 │←────│ 8. Completar    │
│                 │     │ Marca como      │     │                 │
│                 │     │ completada      │     │ 9. Descarga     │
│                 │     │                 │────→│    Excel        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 6. Funcionalidades Nuevas

### 6.1 Panel de Lista de Videos
- Muestra todos los videos subidos por los workers
- Estadísticas: Total, Evaluados, Pendientes
- Filtros: Todos, Pendientes, En Progreso, Completadas
- Búsqueda por Worker ID
- Indicador de estado con colores (verde=completada, amarillo=en progreso, gris=pendiente)
- Botón para copiar Worker ID al portapapeles

### 6.2 Vista de Evaluación
- **Video Player**: Reproducción de videos WebM con controles nativos
- **Selector de videos**: Si hay múltiples videos para un worker/tarea
- **Marcar tiempo**: Captura el timestamp actual del video para la anotación
- **Jump to time**: Click en el tiempo de una anotación para saltar a ese punto del video

### 6.3 Sistema de Anotaciones
- Formulario completo: hora inicio, hora fin, indicador, momento, problema, comentarios
- Tabla de anotaciones con scroll
- Eliminar anotaciones con confirmación
- Contador de anotaciones en tiempo real

### 6.4 Sistema de Problemas
- Formulario: descripción, severidad (Critical/Serious/Cosmetic), tipo (Navigation/Layout/Content/Functionality)
- Lista de problemas identificados
- Eliminar problemas con confirmación
- Contador de problemas en tiempo real

### 6.5 Resumen y Completar
- Contadores en tiempo real: anotaciones, problemas, severidad
- Campo de observaciones generales
- Botón "Marcar como Completada"
- Botón "Reabrir" para evaluaciones completadas

### 6.6 Exportación a Excel
- Genera archivo .xlsx con 7 hojas
- Formato idéntico al Excel de ejemplo del profesor
- Descarga directa desde el navegador

---

## 7. URLs del Sistema

### 7.1 URLs Originales (Workers)

| URL | Método | Vista | Descripción |
|---|---|---|---|
| `/` | GET | redirect | Redirige a `/index/` |
| `/index/` | GET | `ins_page` | Página de instrucciones |
| `/registration/` | GET/POST | `user_registration` | Formulario de registro |
| `/tasks/` | GET | `tasks_info_page` | Video de entrenamiento |
| `/test/<task_id>` | GET | `main_page` | Tarea principal (grabación) |
| `/upload/` | POST | `upload_media` | Subir video grabado |
| `/validate/` | POST | `update_task_answers` | Guardar respuesta |
| `/clickinfo/` | POST | `update_clicks` | Registrar clicks |
| `/statusupdate/` | POST | `Update_Test_Status` | Actualizar estado |
| `/payId/` | GET | `payment_id` | Mostrar Payment ID |
| `/admin/` | GET | Django Admin | Administración |

### 7.2 URLs Nuevas (Evaluación)

| URL | Método | Vista | Descripción |
|---|---|---|---|
| `/evaluacion/` | GET | `lista_videos` | Lista de videos para evaluar |
| `/evaluacion/<payment_id>/<task_id>/` | GET | `evaluar_video` | Vista de evaluación |
| `/evaluacion/video/<payment_id>/<task_id>/<date>/<file>/` | GET | `serve_video` | Servir archivo de video |
| `/evaluacion/<id>/exportar/` | GET | `exportar_excel` | Descargar Excel |
| `/evaluacion/api/<id>/anotacion/` | POST | `agregar_anotacion` | Crear anotación |
| `/evaluacion/api/anotacion/<id>/eliminar/` | POST | `eliminar_anotacion` | Eliminar anotación |
| `/evaluacion/api/<id>/problema/` | POST | `agregar_problema` | Crear problema |
| `/evaluacion/api/problema/<id>/eliminar/` | POST | `eliminar_problema` | Eliminar problema |
| `/evaluacion/api/<id>/completar/` | POST | `completar_evaluacion` | Marcar completada |
| `/evaluacion/api/<id>/reabrir/` | POST | `reabrir_evaluacion` | Reabrir evaluación |

---

## 8. Cómo Ejecutar

### 8.1 Prerequisitos
- Python 3.13
- Entorno virtual creado en `venv/`
- Dependencias instaladas

### 8.2 Pasos

```bash
# 1. Ir a la carpeta del proyecto
cd crowd-ta-UVE

# 2. Activar entorno virtual
venv\Scripts\activate

# 3. Instalar dependencias (si no están instaladas)
venv\Scripts\pip install -r requirements.txt
venv\Scripts\pip install openpyxl

# 4. Ejecutar migraciones
venv\Scripts\python.exe manage.py migrate

# 5. Crear superusuario (si no existe)
venv\Scripts\python.exe manage.py createsuperuser

# 6. Ejecutar servidor
venv\Scripts\python.exe manage.py runserver

# 7. Abrir navegador
```

---

## 9. Accesos

| URL | Usuario | Contraseña | Descripción |
|---|---|---|---|
| `http://localhost:8000/index/` | — | — | Panel de workers |
| `http://localhost:8000/evaluacion/` | `admin` | `admin123` | Panel de evaluación |
| `http://localhost:8000/admin/` | `admin` | `admin123` | Admin de Django |

---

## 10. Exportación a Excel

### 10.1 Estructura del Archivo

El archivo Excel generado contiene **7 hojas**:

| Hoja | Contenido |
|---|---|
| `Interaction table` | Anotaciones del evaluador |
| `Problem` | Problemas identificados |
| `Time annotation` | Tiempo de la evaluación |
| `Event` | Catálogo de 14 indicadores |
| `Context` | Catálogo de 8 momentos de tarea |
| `Severity` | Catálogo de 3 niveles de severidad |
| `Type` | Catálogo de 4 tipos de problema |

### 10.2 Estructura de cada Hoja

#### Interaction table
| Columna | Descripción |
|---|---|
| video_id | Nombre del archivo de video |
| start_time | Hora de inicio del evento (MM:SS) |
| finish_time | Hora de fin del evento (MM:SS) |
| indicator_code | Código del indicador (ACT, DISC, EXE, etc.) |
| task_moment | Momento de la tarea (Instructions, Training, Main task, etc.) |
| problem | Descripción del problema de usabilidad |
| comments | Comentarios adicionales |

#### Problem
| Columna | Descripción |
|---|---|
| problem | Descripción del problema |
| severity | Severidad (Critical, Serious, Cosmetic) |
| type | Tipo (Navigation, Layout, Content, Functionality) |
| comment | Comentarios adicionales |

#### Time annotation
| Columna | Descripción |
|---|---|
| video_id | Nombre del archivo de video |
| annotation_start_time | Hora de inicio de la anotación (HH:MM) |
| annotation_finish_time | Hora de fin de la anotación (HH:MM) |
| duration | Duración total |

---

## 11. Archivos Creados/Modificados

### 11.1 Archivos Nuevos

| Archivo | Líneas | Descripción |
|---|---|---|
| `usabilityTest/evaluation_views.py` | 400 | Vistas del panel de evaluación |
| `usabilityTest/evaluation_urls.py` | 30 | URLs del panel |
| `usabilityTest/templates/evaluation/base_eval.html` | 45 | Template base del panel |
| `usabilityTest/templates/evaluation/lista_videos.html` | 170 | Template de lista de videos |
| `usabilityTest/templates/evaluation/evaluar_video.html` | 555 | Template de evaluación |
| `usabilityTest/static/css/eval_panel.css` | 130 | CSS del panel |
| `usabilityTest/migrations/0005_evaluation_panel_models.py` | Auto | Migración de modelos |
| `usabilityTest/migrations/0006_populate_catalogs.py` | 80 | Población de catálogos |

### 11.2 Archivos Modificados

| Archivo | Cambios |
|---|---|
| `usabilityTest/models.py` | +100 líneas (7 modelos nuevos) |
| `usabilityTest/admin.py` | +80 líneas (9 modelos registrados) |
| `ta_crowdsource/urls.py` | +1 línea (include evaluation_urls) |

---

## Fin del Informe
