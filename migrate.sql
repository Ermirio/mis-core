-- Migration script for MIS-AI Per-Model Variables
USE mis_ai_db;

-- 1. Create new table model_variables
CREATE TABLE IF NOT EXISTS model_variables (
    id INT PRIMARY KEY AUTO_INCREMENT,
    model_id INT NOT NULL,
    opc_variable_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    control_config JSON NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES prediction_models(id) ON DELETE CASCADE,
    FOREIGN KEY (opc_variable_id) REFERENCES opc_variables(id) ON DELETE CASCADE,
    UNIQUE(model_id, opc_variable_id)
);

-- 2. Clean up opc_variables table
DELIMITER $$

DROP PROCEDURE IF EXISTS UpgradeDatabase$$

CREATE PROCEDURE UpgradeDatabase()
BEGIN
    -- Drop Foreign Key 'fk_opc_target' if exists
    IF EXISTS (SELECT * FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'opc_variables' AND CONSTRAINT_NAME = 'fk_opc_target') THEN
        ALTER TABLE opc_variables DROP FOREIGN KEY fk_opc_target;
    END IF;

    -- Drop Foreign Key 'fk_opc_variables_target' if exists (This was the one causing error)
    IF EXISTS (SELECT * FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'opc_variables' AND CONSTRAINT_NAME = 'fk_opc_variables_target') THEN
        ALTER TABLE opc_variables DROP FOREIGN KEY fk_opc_variables_target;
    END IF;

    -- Drop Columns if exist
    IF EXISTS (SELECT * FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'opc_variables' AND COLUMN_NAME = 'target_id') THEN
        ALTER TABLE opc_variables DROP COLUMN target_id;
    END IF;

    IF EXISTS (SELECT * FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'opc_variables' AND COLUMN_NAME = 'control_config') THEN
        ALTER TABLE opc_variables DROP COLUMN control_config;
    END IF;

    IF EXISTS (SELECT * FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'opc_variables' AND COLUMN_NAME = 'type_category') THEN
        ALTER TABLE opc_variables DROP COLUMN type_category;
    END IF;
END $$

DELIMITER ;

CALL UpgradeDatabase();
DROP PROCEDURE UpgradeDatabase;
