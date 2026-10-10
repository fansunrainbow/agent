-- Execute manually in MySQL Workbench as an authorized DBA.
-- Replace YOUR_PASSWORD_HERE in Workbench only. Never save the real password here.
CREATE USER IF NOT EXISTS 'agent_readonly_user'@'localhost' IDENTIFIED BY 'YOUR_PASSWORD_HERE';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'agent_readonly_user'@'localhost';
GRANT SELECT ON `agentic_marketing`.* TO 'agent_readonly_user'@'localhost';
FLUSH PRIVILEGES;
SHOW GRANTS FOR 'agent_readonly_user'@'localhost';
