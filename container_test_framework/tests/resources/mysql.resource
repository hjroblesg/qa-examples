*** Settings ***
Documentation     Reusable keywords for the MySQL functional/integration suite.
...
...               Container lifecycle is driven THROUGH THE CTF ENGINE (the
...               framework's own CLI: `python -m ctf ...`), so the functional
...               layer dogfoods the same engine the unit tests cover. DB
...               connectivity uses DatabaseLibrary + PyMySQL.
...
...               Requires the package importable: `pip install -e .`.
Library           Process
Library           OperatingSystem
Library           DatabaseLibrary


*** Variables ***
# Overridable from the CLI with:  robot --variable DB_HOST:1.2.3.4 ...
${IMAGE}          mysql
${TAG}            8.0
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
    [Documentation]    Launch MySQL through the ctf engine, publishing 3306 and
    ...                passing the root password + database as env vars.
    # NB: '=' is escaped (\=) so Run Process passes these as literal positional
    # args rather than treating them as Robot named arguments.
    ${result}=    Run Process    ${{sys.executable}}    -m    ctf
    ...    --command    run_container    --image    ${IMAGE}    --tag    ${TAG}
    ...    --run-opts\=-d
    ...    --publish    ${DB_PORT}:3306
    ...    --env    MYSQL_ROOT_PASSWORD\=${DB_PASS}    MYSQL_DATABASE\=${DB_NAME}
    Log    ${result.stdout}
    # The ctf CLI now exits non-zero on a failed run, so this catches it directly.
    Should Be Equal As Integers    ${result.rc}    0
    ...    msg=ctf run_container failed: ${result.stdout} ${result.stderr}    values=False

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
    [Documentation]    Full teardown through the ctf engine; never fails the run.
    Run Keyword And Ignore Error    Disconnect From Database
    Run Process    ${{sys.executable}}    -m    ctf
    ...    --command    rm_container    --image    ${IMAGE}    --tag    ${TAG}
