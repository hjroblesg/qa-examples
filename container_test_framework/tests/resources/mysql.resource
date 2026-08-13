*** Settings ***
Documentation     Reusable keywords for the MySQL functional/integration suite:
...               container lifecycle (via the docker CLI) and DB connectivity
...               (via DatabaseLibrary + PyMySQL). Kept separate from the test
...               cases so the same setup can back future MySQL suites.
Library           Process
Library           OperatingSystem
Library           DatabaseLibrary


*** Variables ***
# Overridable from the CLI with:  robot --variable DB_HOST:1.2.3.4 ...
${IMAGE}          mysql
${TAG}            8.0
${CONTAINER}      ctf-mysql-${TAG}
${DB_MODULE}      pymysql
${DB_NAME}        testdb
${DB_USER}        root
${DB_PASS}        ctf-secret
${DB_HOST}        127.0.0.1
${DB_PORT}        3306
${READY_TIMEOUT}    90s
${READY_INTERVAL}    3s


*** Keywords ***
Start MySQL Container
    [Documentation]    Launch a throwaway MySQL container with a known root
    ...                password and database, publishing 3306 to the host.
    # NB: the env tokens escape '=' (MYSQL_ROOT_PASSWORD\=...) so Run Process
    # treats them as literal positional args, not Robot named arguments.
    ${result}=    Run Process    docker    run    -d    --name    ${CONTAINER}
    ...    -e    MYSQL_ROOT_PASSWORD\=${DB_PASS}
    ...    -e    MYSQL_DATABASE\=${DB_NAME}
    ...    -p    ${DB_PORT}:3306
    ...    ${IMAGE}:${TAG}
    Should Be Equal As Integers    ${result.rc}    0
    ...    msg=Failed to start container: ${result.stderr}    values=False

Wait Until MySQL Is Ready
    [Documentation]    Retry connecting until the server accepts connections
    ...                (first boot takes several seconds).
    Wait Until Keyword Succeeds    ${READY_TIMEOUT}    ${READY_INTERVAL}
    ...    Connect To MySQL

Connect To MySQL
    Connect To Database    ${DB_MODULE}    ${DB_NAME}    ${DB_USER}    ${DB_PASS}
    ...    ${DB_HOST}    ${DB_PORT}
    ${rows}=    Query    SELECT 1
    Should Be Equal As Integers    ${rows[0][0]}    1

Seed Schema
    [Documentation]    Create a representative table so schema checks have a
    ...                real target.
    Execute Sql String    DROP TABLE IF EXISTS users
    Execute Sql String    CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR(255), created_at DATETIME)

Open MySQL Under Test
    [Documentation]    Full bring-up used by Suite Setup.
    Start MySQL Container
    Wait Until MySQL Is Ready
    Seed Schema

Close MySQL Under Test
    [Documentation]    Full teardown used by Suite Teardown; never fails the run.
    Run Keyword And Ignore Error    Disconnect From Database
    Run Process    docker    rm    -f    ${CONTAINER}
