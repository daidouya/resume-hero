CREATE DATABASE IF NOT EXISTS resumeapp;

USE resumeapp;

DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs
(
    jobid             int not null AUTO_INCREMENT,
    bucketkey  varchar(256) not null, 
    ratingbucketkey       varchar(256) not null, 
    advicebucketkey    varchar(256) not null,  
    letterbucketkey    varchar(256) not null, 
);


ALTER TABLE jobs AUTO_INCREMENT = 1001;

DROP USER IF EXISTS 'resumeapp-read-write';

CREATE USER 'resumeapp-read-write' IDENTIFIED BY 'def456!!';

GRANT SELECT, SHOW VIEW, INSERT, UPDATE, DELETE, DROP, CREATE, ALTER ON resumeapp.* 
      TO 'resumeapp-read-write';
