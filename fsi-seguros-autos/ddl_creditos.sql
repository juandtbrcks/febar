-- FSI — BD de créditos personales (proxy AWS). BD: creditos_aws

DROP SCHEMA IF EXISTS seguros_creditos CASCADE;
CREATE SCHEMA seguros_creditos;

-- ============================ CRÉDITOS (AWS) ============================
CREATE TABLE seguros_creditos.creditos_personales (
  credito_id        BIGINT PRIMARY KEY,
  customer_id       INT,            -- mismo id_cliente del grupo (no siempre lo hay)
  customer_rfc      VARCHAR(13),
  product           VARCHAR(30),    -- Personal / Nómina / Auto / PyME
  origination_date  DATE,
  term_months       INT,
  amount            NUMERIC(14,2),
  rate_pct          NUMERIC(6,2),
  balance           NUMERIC(14,2),
  days_past_due     INT,
  status            VARCHAR(15)     -- current / delinquent / default / paid_off
);
