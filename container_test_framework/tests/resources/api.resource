*** Settings ***
Documentation     Reusable keywords for the REST API functional suite:
...               container lifecycle (via the docker CLI) and an HTTP session
...               (via RequestsLibrary). Target is mccutchen/go-httpbin — a
...               maintained, multi-arch httpbin that listens on :8080.
Library           Process
Library           RequestsLibrary


*** Variables ***
# Overridable from the CLI:  robot --variable BASE_URL:http://host:8080 ...
${IMAGE}          mccutchen/go-httpbin
${TAG}            v2.15.0
${CONTAINER}      ctf-go-httpbin
${HOST_PORT}      8080
${CONTAINER_PORT}    8080
${BASE_URL}       http://127.0.0.1:${HOST_PORT}
${SESSION}        api
${READY_TIMEOUT}    30s
${READY_INTERVAL}    1s


*** Keywords ***
Start API Container
    [Documentation]    Launch go-httpbin, publishing its port to the host.
    ${result}=    Run Process    docker    run    -d    --name    ${CONTAINER}
    ...    -p    ${HOST_PORT}:${CONTAINER_PORT}
    ...    ${IMAGE}:${TAG}
    Should Be Equal As Integers    ${result.rc}    0
    ...    msg=Failed to start container: ${result.stderr}    values=False

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
    [Documentation]    Full teardown used by Suite Teardown; never fails the run.
    Run Process    docker    rm    -f    ${CONTAINER}
