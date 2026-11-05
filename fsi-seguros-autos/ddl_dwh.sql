-- Aseguradora FSI · Autos — DWH "legacy" (proxy Oracle on-prem 2011). BD: dwh_seguros
-- Nombres estilo legacy (tb_*, abreviaturas) a propósito.

DROP SCHEMA IF EXISTS seguros_dwh CASCADE;
CREATE SCHEMA seguros_dwh;

-- ============================ DWH SEGUROS ============================
CREATE TABLE seguros_dwh.tb_productos (
  id_producto      INT PRIMARY KEY,
  cve_producto     VARCHAR(12),
  nombre_producto  VARCHAR(80),
  ramo             VARCHAR(20),     -- Autos
  subramo          VARCHAR(40)
);

CREATE TABLE seguros_dwh.tb_agentes (
  id_agente        INT PRIMARY KEY,
  cve_agente       VARCHAR(10),
  nombre_agente    VARCHAR(120),
  canal            VARCHAR(30),     -- Agente / Banca Seguros / Tienda Aliada / Digital / Broker
  oficina          VARCHAR(60),
  region           VARCHAR(30),
  fecha_alta       DATE,
  activo           BOOLEAN
);

CREATE TABLE seguros_dwh.tb_clientes (
  id_cliente       INT PRIMARY KEY,
  nombre           VARCHAR(60),
  apellido_paterno VARCHAR(40),
  apellido_materno VARCHAR(40),
  rfc              VARCHAR(13),
  curp             VARCHAR(18),
  fecha_nacimiento DATE,
  genero           CHAR(1),
  email            VARCHAR(120),
  telefono         VARCHAR(15),
  estado           VARCHAR(40),
  municipio        VARCHAR(60),
  codigo_postal    VARCHAR(5),
  fecha_alta       DATE,
  segmento         VARCHAR(20)      -- Masivo / Preferente / Patrimonial / PyME
);

CREATE TABLE seguros_dwh.tb_polizas (
  id_poliza         BIGINT PRIMARY KEY,
  num_poliza        VARCHAR(20),
  id_cliente        INT,
  id_producto       INT,
  id_agente         INT,
  fecha_emision     DATE,
  inicio_vigencia   DATE,
  fin_vigencia      DATE,
  suma_asegurada    NUMERIC(14,2),
  prima_neta_anual  NUMERIC(12,2),
  forma_pago        VARCHAR(12),    -- Anual / Semestral / Trimestral / Mensual
  estatus           VARCHAR(12),    -- Vigente / Vencida / Cancelada
  fecha_cancelacion DATE,
  es_renovacion     BOOLEAN
);

CREATE TABLE seguros_dwh.tb_vehiculos (
  id_vehiculo      BIGINT PRIMARY KEY,
  id_poliza        BIGINT,
  marca            VARCHAR(30),
  submarca         VARCHAR(30),
  anio_modelo      INT,
  uso              VARCHAR(20),     -- Particular / Plataforma / Carga ligera
  valor_comercial  NUMERIC(12,2),
  num_serie_vin    VARCHAR(17),
  placas           VARCHAR(10),
  app_conectada    BOOLEAN          -- asegurado usa la app de autos (telemetría)
);

CREATE TABLE seguros_dwh.tb_coberturas (
  id_cobertura          INT PRIMARY KEY,
  cve_cobertura         VARCHAR(5),
  nombre_cobertura      VARCHAR(60),
  tipo                  VARCHAR(12),   -- Básica / Adicional / Servicio
  deducible_pct_default NUMERIC(5,2)
);

CREATE TABLE seguros_dwh.tb_poliza_coberturas (
  id_poliza        BIGINT,
  id_cobertura     INT,
  suma_asegurada   NUMERIC(14,2),    -- NULL = amparada / servicio
  deducible_pct    NUMERIC(5,2),
  prima_cobertura  NUMERIC(12,2),
  PRIMARY KEY (id_poliza, id_cobertura)
);

CREATE TABLE seguros_dwh.tb_conductores (
  id_conductor     BIGINT PRIMARY KEY,
  id_poliza        BIGINT,
  id_cliente       INT,              -- NULL si no es el contratante
  es_titular       BOOLEAN,
  edad             INT,
  genero           CHAR(1),
  anios_licencia   INT,
  tipo_licencia    VARCHAR(15),
  codigo_postal    VARCHAR(5)
);

CREATE TABLE seguros_dwh.tb_cotizaciones (
  id_cotizacion    BIGINT PRIMARY KEY,
  fecha_cotizacion DATE,
  canal            VARCHAR(30),      -- App Autos FSI / Portal Web / Comparador Externo / Agente / Módulo Tienda Aliada
  sistema_origen   VARCHAR(20),      -- APP_AUTOS / PORTAL_WEB / API_COMPARADOR / SISE
  codigo_postal    VARCHAR(5),
  estado           VARCHAR(40),
  marca            VARCHAR(30),
  submarca         VARCHAR(30),
  anio_modelo      INT,
  edad_conductor   INT,
  id_producto      INT,
  prima_cotizada   NUMERIC(12,2),
  convertida       BOOLEAN,
  id_poliza        BIGINT
);

CREATE TABLE seguros_dwh.tb_asistencias (
  id_asistencia     BIGINT PRIMARY KEY,
  id_poliza         BIGINT,
  fecha_solicitud   TIMESTAMP,
  tipo_servicio     VARCHAR(30),     -- Grúa / Paso de corriente / Cambio de llanta / ...
  canal_solicitud   VARCHAR(15),     -- App / Call Center
  estado            VARCHAR(40),
  proveedor         VARCHAR(60),
  tiempo_arribo_min INT,
  costo             NUMERIC(10,2),
  calificacion      INT,             -- 1-5
  estatus           VARCHAR(12)      -- Concluida / Cancelada
);

CREATE TABLE seguros_dwh.tb_recibos (
  id_recibo         BIGINT PRIMARY KEY,
  id_poliza         BIGINT,
  num_recibo        INT,
  fecha_vencimiento DATE,
  fecha_pago        DATE,
  importe           NUMERIC(12,2),
  estatus           VARCHAR(12)     -- Pagado / Pendiente / Cancelado
);

CREATE TABLE seguros_dwh.tb_ajustadores (
  id_ajustador     INT PRIMARY KEY,
  nombre_ajustador VARCHAR(120),
  region           VARCHAR(30),
  tipo             VARCHAR(12)      -- Interno / Despacho
);

CREATE TABLE seguros_dwh.tb_talleres (
  id_taller        INT PRIMARY KEY,
  nombre_taller    VARCHAR(120),
  tipo             VARCHAR(20),     -- Agencia / Multimarca / Independiente
  estado           VARCHAR(40),
  municipio        VARCHAR(60)
);

CREATE TABLE seguros_dwh.tb_siniestros (
  id_siniestro       BIGINT PRIMARY KEY,
  num_siniestro      VARCHAR(20),
  id_poliza          BIGINT,
  id_ajustador       INT,
  id_taller          INT,           -- solo Autos
  fecha_ocurrencia   TIMESTAMP,
  fecha_reporte      TIMESTAMP,
  cobertura          VARCHAR(40),
  causa              VARCHAR(60),
  estado_ocurrencia  VARCHAR(40),
  canal_reporte      VARCHAR(20),   -- App / Call Center / Agente / Sucursal
  monto_reclamado    NUMERIC(14,2),
  reserva_inicial    NUMERIC(14,2),
  deducible          NUMERIC(12,2),
  reporte_autoridad  BOOLEAN,       -- MP / tránsito / parte policial
  num_terceros       INT,
  estatus            VARCHAR(20),   -- Abierto / Cerrado / Rechazado / En investigación
  fecha_cierre       DATE,
  fraude_confirmado  BOOLEAN        -- dictamen SIU (solo casos cerrados/rechazados)
);

CREATE TABLE seguros_dwh.tb_movtos_siniestro (
  id_movimiento    BIGINT PRIMARY KEY,
  id_siniestro     BIGINT,
  fecha_movimiento DATE,
  tipo_movimiento  VARCHAR(20),     -- Pago / Ajuste Reserva / Recuperación
  importe          NUMERIC(14,2)
);

CREATE TABLE seguros_dwh.tb_valuaciones (
  id_valuacion             BIGINT PRIMARY KEY,
  id_siniestro             BIGINT,
  id_taller                INT,
  fecha_valuacion          DATE,
  monto_presupuesto_taller NUMERIC(14,2),
  monto_autorizado         NUMERIC(14,2),
  num_piezas               INT,
  pct_piezas_originales    NUMERIC(4,2),
  horas_mano_obra          NUMERIC(6,1),
  dias_reparacion          INT
);

CREATE TABLE seguros_dwh.tb_terceros_siniestro (
  id_tercero              BIGINT PRIMARY KEY,
  id_siniestro            BIGINT,
  tipo_tercero            VARCHAR(12),  -- Vehículo / Peatón / Propiedad
  nombre_tercero          VARCHAR(120),
  telefono_tercero        VARCHAR(15),
  placas_tercero          VARCHAR(10),
  aseguradora_tercero     VARCHAR(20),
  monto_reclamado_tercero NUMERIC(14,2)
);

-- Tabla "consolidada" legacy: el síntoma de las 55K columnas (duplicados de
-- columnas con distintos nombres/formatos y valores inconsistentes).
CREATE TABLE seguros_dwh.tb_cliente_consolidado_2011 (
  id_cliente        INT,
  nombre_cliente    VARCHAR(150),
  nom_cte           VARCHAR(150),
  nombre_completo   VARCHAR(150),
  rfc               VARCHAR(13),
  rfc_cliente       VARCHAR(13),
  rfc_cte_ant       VARCHAR(13),
  curp              VARCHAR(18),
  curp_cte          VARCHAR(18),
  fec_nac           VARCHAR(10),
  fecha_nacimiento  DATE,
  fch_nacimiento_cte VARCHAR(8),
  email             VARCHAR(120),
  correo_e          VARCHAR(120),
  mail_contacto     VARCHAR(120),
  tel               VARCHAR(15),
  telefono_casa     VARCHAR(15),
  tel_contacto_1    VARCHAR(15),
  edo               VARCHAR(40),
  estado_residencia VARCHAR(40),
  cve_edo           VARCHAR(3),
  cp                VARCHAR(5),
  cod_postal        VARCHAR(5),
  segmento          VARCHAR(20),
  seg_cte           VARCHAR(20),
  num_polizas_vig   INT,
  tot_polizas       INT,
  prima_total       NUMERIC(14,2),
  prima_tot_anual   NUMERIC(14,2),
  fec_ult_act       VARCHAR(10),
  usr_ult_act       VARCHAR(20),
  origen_carga      VARCHAR(20)
);
