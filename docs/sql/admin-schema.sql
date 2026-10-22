CREATE TABLE IF NOT EXISTS admins (
	id INTEGER NOT NULL,
	username VARCHAR(80) NOT NULL,
	password_hash VARCHAR(300) NOT NULL,
	PRIMARY KEY (id),
	CHECK (id = 1),
	UNIQUE (username)
);
