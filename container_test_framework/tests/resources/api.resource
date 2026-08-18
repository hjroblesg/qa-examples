*** Settings ***
Documentation     Reusable keywords for the REST API functional suite.
...
...               Container lifecycle is driven THROUGH THE CTF ENGINE (the
...               framework's own CLI: `python -m ctf ...`); the HTTP session
...               uses RequestsLibrary. Target is mccutchen/go-httpbin — a
...               maintained, multi-arch httpbin that listens on :8080.
...
...               Requires the package importable: `pip install -e .`.
Library           Process
Library           RequestsLibrary


*** Variables ***
# Overridable from the CLI:  robot --variable BASE_URL:http://host:8080 ...
${IMAGE}          mccutchen/go-httpbin
${TAG}            v2.15.0
${HOST_PORT}      8080
${CONTAINER_PORT}    8080
${BASE_URL}       http://127.0.0.1:${HOST_PORT}
${SESSION}        api
${READY_TIMEOUT}    30s
${READY_INTERVAL}    1s


*** Keywords ***
Start API Container
    [Documentation]    Launch go-httpbin through the ctf engine, publishing its
    ...                port to the host.
    ${result}=    Run Process    ${{sys.executable}}    -m    ctf
    ...    --command    run_container    --image    ${IMAGE}    --tag    ${TAG}
    ...    --run-opts\=-d
    ...    --publish    ${HOST_PORT}:${CONTAINER_PORT}
    Log    ${result.stdout}
    # The ctf CLI now exits non-zero on a failed run, so this catches it directly.
    Should Be Equal As Integers    ${result.rc}    0
    ...    msg=ctf run_container failed: ${result.stdout} ${result.stderr}    values=False

Wait Until API Is Ready
    [Documentation]    Retry a request until the server responds.
    Wait Until Keyword Succeeds    ${READY_TIMEOUT}    ${READY_INTERVAL}
    ...    Ping API

Ping API
    Create Session    ${SESSION}    ${BASE_URL}
    ${resp}=    GET On Session    ${SESSION}    /status/200
    Should Be Equal As Integers    ${resp.status_code}    200

Open API Under Test
    [Documentation]    Full bring-up used by Suite Setup.
    Start API Container
    Wait Until API Is Ready

Close API Under Test
    [Documentation]    Full teardown through the ctf engine; never fails the run.
    Run Process    ${{sys.executable}}    -m    ctf
    ...    --command    rm_container    --image    ${IMAGE}    --tag    ${TAG}
