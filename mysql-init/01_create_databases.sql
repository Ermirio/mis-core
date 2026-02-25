CREATE DATABASE IF NOT EXISTS mis_core_db;
CREATE DATABASE IF NOT EXISTS mis_energy_db;
CREATE DATABASE IF NOT EXISTS mis_ai_db;
CREATE DATABASE IF NOT EXISTS mis_changeover_db;

-- Fix for MySQL 8.0: Create user explicitly before granting
-- The password 'mis123' should match MYSQL_PASSWORD env if possible, 
-- but here we are setting up a root-like user 'mis' often used by legacy parts.
CREATE USER IF NOT EXISTS 'mis'@'%' IDENTIFIED BY 'mis123';

-- Grant privileges
-- Grant privileges to 'mis'
GRANT ALL PRIVILEGES ON *.* TO 'mis'@'%' WITH GRANT OPTION;

-- Fix for 'mis2' (used in .env) accessing other DBs (like mis_ai_db)
CREATE USER IF NOT EXISTS 'mis2'@'%' IDENTIFIED BY 'mis123';
GRANT ALL PRIVILEGES ON *.* TO 'mis2'@'%' WITH GRANT OPTION;

FLUSH PRIVILEGES;
