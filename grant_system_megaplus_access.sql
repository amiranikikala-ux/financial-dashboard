-- Grant NT AUTHORITY\SYSTEM full access needed to ingest MegaPlus backups:
--   - read existing MEGAPLUS_<storeID> databases (db_datareader)
--   - restore new backups over existing databases (db_owner — RESTORE WITH REPLACE + ALTER DATABASE SET SINGLE/MULTI_USER)
--   - create databases for new store IDs that show up later (dbcreator server role)
-- Run once with admin rights. Idempotent — safe to re-run.

USE master;
GO

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'NT AUTHORITY\SYSTEM')
    CREATE LOGIN [NT AUTHORITY\SYSTEM] FROM WINDOWS;
GO

ALTER SERVER ROLE dbcreator ADD MEMBER [NT AUTHORITY\SYSTEM];
GO

USE MEGAPLUS_1329;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'NT AUTHORITY\SYSTEM')
    CREATE USER [NT AUTHORITY\SYSTEM] FOR LOGIN [NT AUTHORITY\SYSTEM];
GO
ALTER ROLE db_datareader ADD MEMBER [NT AUTHORITY\SYSTEM];
GO
ALTER ROLE db_owner ADD MEMBER [NT AUTHORITY\SYSTEM];
GO

USE MEGAPLUS_1301;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'NT AUTHORITY\SYSTEM')
    CREATE USER [NT AUTHORITY\SYSTEM] FOR LOGIN [NT AUTHORITY\SYSTEM];
GO
ALTER ROLE db_datareader ADD MEMBER [NT AUTHORITY\SYSTEM];
GO
ALTER ROLE db_owner ADD MEMBER [NT AUTHORITY\SYSTEM];
GO

PRINT 'Done. NT AUTHORITY\SYSTEM has dbcreator + db_owner + db_datareader on MEGAPLUS_1329 and MEGAPLUS_1301.';
