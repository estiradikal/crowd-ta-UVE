import sqlite3

# Nos conectamos a la base de datos
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Creamos las tablas de Javier con las columnas exactas que necesita su código
queries = [
    '''DROP TABLE IF EXISTS "usabilityTest_catalogoproblema";''',
    '''CREATE TABLE "usabilityTest_catalogoproblema" (
        "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
        "codigo" varchar(16) NOT NULL UNIQUE DEFAULT "",
        "descripcion" text NOT NULL,
        "fecha_creacion" datetime NOT NULL
    );''',
    '''DROP TABLE IF EXISTS "usabilityTest_evaluacion";''',
    '''CREATE TABLE "usabilityTest_evaluacion" (
        "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
        "video_id" varchar(256) NOT NULL,
        "payment_id" varchar(256) NOT NULL,
        "task_id" varchar(32) NOT NULL,
        "completada" bool NOT NULL,
        "evaluador" varchar(128) NULL,
        "fecha_inicio" datetime NULL,
        "fecha_fin" datetime NULL,
        "observaciones_generales" text NOT NULL,
        "tiempo_activo_segundos" integer unsigned NOT NULL CHECK ("tiempo_activo_segundos" >= 0)
    );''',
    '''DROP TABLE IF EXISTS "usabilityTest_anotacion";''',
    '''CREATE TABLE "usabilityTest_anotacion" (
        "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
        "start_time" varchar(16) NOT NULL,
        "finish_time" varchar(16) NOT NULL,
        "indicador" varchar(16) NOT NULL,
        "contexto" varchar(64) NOT NULL,
        "problema" text NOT NULL,
        "comentarios" text NOT NULL,
        "fecha_creacion" datetime NOT NULL,
        "evaluacion_id" integer NOT NULL REFERENCES "usabilityTest_evaluacion" ("id") DEFERRABLE INITIALLY DEFERRED,
        "problema_ref_id" integer NULL REFERENCES "usabilityTest_catalogoproblema" ("id") DEFERRABLE INITIALLY DEFERRED
    );''',
    '''DROP TABLE IF EXISTS "usabilityTest_problemaidentificado";''',
    '''CREATE TABLE "usabilityTest_problemaidentificado" (
        "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
        "severidad" varchar(32) NOT NULL,
        "tipo" varchar(32) NOT NULL,
        "comentarios" text NOT NULL,
        "fecha_creacion" datetime NOT NULL,
        "evaluacion_id" integer NOT NULL REFERENCES "usabilityTest_evaluacion" ("id") DEFERRABLE INITIALLY DEFERRED,
        "problema_id" integer NOT NULL REFERENCES "usabilityTest_catalogoproblema" ("id") DEFERRABLE INITIALLY DEFERRED
    );'''
]

for q in queries:
    cursor.execute(q)

conn.commit()
conn.close()
print("✅ Tablas de Javier creadas correctamente en esta rama.")