*** Settings ***
Documentation     REST API functional / integration suite.
...
...               Mirrors the three dimensions covered by the APIValidator unit
...               tests (ctf.validators.api), exercised against a REAL
...               go-httpbin container: health, status codes (incl. negatives),
...               and response contract. Requires a running Docker daemon.
...
...               Run:    robot tests/rest_api_tests.robot
...               Deps:   pip install robotframework robotframework-requests
Resource          resources/api.resource
Library           RequestsLibrary
Library           Collections
Suite Setup       Open API Under Test
Suite Teardown    Close API Under Test


*** Test Cases ***
Health Endpoint Returns 200
    [Documentation]    The API is reachable and returns the expected status.
    [Tags]    smoke    health
    Create Session    ${SESSION}    ${BASE_URL}
    ${resp}=    GET On Session    ${SESSION}    /status/200
    Should Be Equal As Integers    ${resp.status_code}    200

Unknown Path Returns 404
    [Documentation]    A negative status-code case is reported correctly.
    [Tags]    status    negative
    Create Session    ${SESSION}    ${BASE_URL}
    ${resp}=    GET On Session    ${SESSION}    /status/404    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    404

GET Response Contract Has Expected Keys
    [Documentation]    The JSON body contains the expected top-level keys.
    [Tags]    contract
    Create Session    ${SESSION}    ${BASE_URL}
    ${resp}=    GET On Session    ${SESSION}    /get
    Should Be Equal As Integers    ${resp.status_code}    200
    Dictionary Should Contain Key    ${resp.json()}    url
    Dictionary Should Contain Key    ${resp.json()}    headers
    Dictionary Should Contain Key    ${resp.json()}    args

Query Parameters Are Echoed Back
    [Documentation]    Query params round-trip through the /get endpoint.
    ...                Note: go-httpbin returns each arg as a LIST of values
    ...                (a query key may repeat), so we assert membership.
    [Tags]    contract
    Create Session    ${SESSION}    ${BASE_URL}
    ${params}=    Create Dictionary    name=Hector    role=QA
    ${resp}=    GET On Session    ${SESSION}    /get    params=${params}
    Should Be Equal As Integers    ${resp.status_code}    200
    ${args}=    Set Variable    ${resp.json()['args']}
    Should Contain    ${args['name']}    Hector
    Should Contain    ${args['role']}    QA

POST JSON Body Is Echoed Back
    [Documentation]    A JSON body is accepted and reflected under 'json'.
    [Tags]    contract
    Create Session    ${SESSION}    ${BASE_URL}
    ${body}=    Create Dictionary    name=Hector    role=Engineer
    ${resp}=    POST On Session    ${SESSION}    /post    json=${body}
    Should Be Equal As Integers    ${resp.status_code}    200
    Dictionary Should Contain Item    ${resp.json()['json']}    name    Hector

Basic Auth Rejects Missing Credentials
    [Documentation]    Protected endpoint returns 401 without credentials.
    [Tags]    auth    negative
    Create Session    ${SESSION}    ${BASE_URL}
    ${resp}=    GET On Session    ${SESSION}    /basic-auth/user/pass    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    401
