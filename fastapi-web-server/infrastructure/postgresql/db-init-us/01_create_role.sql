-- Development-only example role and password. Not for real deployment.
CREATE USER uudex_user WITH
	LOGIN
	SUPERUSER
	NOCREATEDB
	NOCREATEROLE
	INHERIT
	NOREPLICATION
	CONNECTION LIMIT -1
	PASSWORD 'uudex';
