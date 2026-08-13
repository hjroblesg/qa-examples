*** Settings ***
Documentation     MySQL functional / integration suite.
...
...               Mirrors the four dimensions covered by the MySQLValidator unit
...               tests (ctf.validators.mysql), but exercised against a REAL
...               MySQL container: connectivity/health, schema, CRUD, and data
...               integrity. Requires a running Docker daemon.
...
...               Run:    robot tests/mysql_tests.robot
...               Deps:   pip install robotframework robotframework-databaselibrary pymysql
Resource          resources/mysql.resource
Suite Setup       Open MySQL Under Test
Suite Teardown    Close MySQL Under Test


*** Test Cases ***
Health Check MySQL Is Reachable
    [Documentation]    The server accepts connections and answers a trivial query.
    [Tags]    smoke    health
    ${rows}=    Query    SELECT 1
    Should Be Equal As Integers    ${rows[0][0]}    1

Schema Has Expected Table And Columns
    [Documentation]    The seeded table exists and has the expected columns.
    [Tags]    schema
    Table Must Exist    users
    Check If Exists In Database    SELECT column_name FROM information_schema.columns WHERE table_schema='${DB_NAME}' AND table_name='users' AND column_name='email'

Schema Missing Column Is Detected
    [Documentation]    A column that does not exist is correctly reported absent.
    [Tags]    schema    negative
    Check If Not Exists In Database    SELECT column_name FROM information_schema.columns WHERE table_schema='${DB_NAME}' AND table_name='users' AND column_name='phone'

CRUD Round Trip Behaves
    [Documentation]    Insert -> select -> update -> select -> delete all behave.
    [Tags]    crud
    Execute Sql String    CREATE TABLE _ctf_healthcheck (id INT PRIMARY KEY, name VARCHAR(50))
    Execute Sql String    INSERT INTO _ctf_healthcheck (id, name) VALUES (1, 'alpha')
    Check If Exists In Database    SELECT 1 FROM _ctf_healthcheck WHERE id=1 AND name='alpha'
    Execute Sql String    UPDATE _ctf_healthcheck SET name='beta' WHERE id=1
    Check If Exists In Database    SELECT 1 FROM _ctf_healthcheck WHERE id=1 AND name='beta'
    Execute Sql String    DELETE FROM _ctf_healthcheck WHERE id=1
    Row Count Is 0    SELECT * FROM _ctf_healthcheck
    [Teardown]    Execute Sql String    DROP TABLE IF EXISTS _ctf_healthcheck

Data Integrity Primary Key Uniqueness Enforced
    [Documentation]    A duplicate primary key is rejected by the database.
    [Tags]    integrity    negative
    Execute Sql String    CREATE TABLE _ctf_pk (id INT PRIMARY KEY)
    Execute Sql String    INSERT INTO _ctf_pk (id) VALUES (1)
    Run Keyword And Expect Error    *
    ...    Execute Sql String    INSERT INTO _ctf_pk (id) VALUES (1)
    [Teardown]    Execute Sql String    DROP TABLE IF EXISTS _ctf_pk
