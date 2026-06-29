-- COFRAP : schéma de la base d'authentification
-- Une seule table conforme au cahier des charges.
CREATE TABLE IF NOT EXISTS users (
    id       SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password TEXT NOT NULL,                 -- hash bcrypt du mot de passe
    mfa      TEXT NOT NULL DEFAULT '',      -- secret TOTP chiffré (Fernet)
    gendate  BIGINT,                        -- date de génération (epoch UTC, s)
    expired  SMALLINT DEFAULT 0             -- 0 = actif, 1 = expiré
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
