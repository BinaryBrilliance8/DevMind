
CREATE TABLE runs (
	id VARCHAR(36) NOT NULL, 
	request_key VARCHAR(128) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	request JSON NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	phase VARCHAR(24) NOT NULL, 
	owner VARCHAR(36), 
	lease FLOAT, 
	created FLOAT NOT NULL, 
	updated FLOAT NOT NULL, 
	result JSON, 
	review JSON, 
	PRIMARY KEY (id), 
	UNIQUE (request_key)
)

;

CREATE INDEX run_queue ON runs (status, created);

CREATE INDEX run_leases ON runs (status, lease);


CREATE TABLE schema_version (
	singleton SERIAL NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (singleton)
)

;


CREATE TABLE artifacts (
	run_id VARCHAR(36) NOT NULL, 
	name VARCHAR(40) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	content TEXT NOT NULL, 
	PRIMARY KEY (run_id, name), 
	FOREIGN KEY(run_id) REFERENCES runs (id)
)

;


CREATE TABLE events (
	sequence SERIAL NOT NULL, 
	run_id VARCHAR(36) NOT NULL, 
	at FLOAT NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (sequence), 
	FOREIGN KEY(run_id) REFERENCES runs (id)
)

;

CREATE INDEX run_events ON events (run_id, sequence);
