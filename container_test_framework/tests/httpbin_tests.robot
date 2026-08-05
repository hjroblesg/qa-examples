*** Settings ***
Library    RequestsLibrary
Library    Collections

*** Variables ***
${BASE_URL}    http://httpbin:80    # inside Docker network
# If testing locally without Compose, use http://localhost:8080

*** Test Cases ***

Simple GET On Session
    [Tags]    smoke
    Create Session    api    ${BASE_URL}
    ${resp}=    GET On Session    api    /get
    Log     TEXT: ${resp.text} 
    Should Be Equal As Integers    ${resp.status_code}    200
    Dictionary Should Contain Key    ${resp.json()}    headers

GET With Query Parameters
    [Tags]    regression
    Create Session    api    ${BASE_URL}
    ${resp}=    GET On Session    api    url=${BASEURL}/get?name=Hector&role=QA
    Log     TEXT: ${resp.text} 
    Should Be Equal As Integers    ${resp.status_code}    200
    Dictionary Should Contain Value    ${resp.json()["args"]}    Hector
    Dictionary Should Contain Value    ${resp.json()["args"]}    QA

POST With JSON Body
    [Tags]    regression
    Create Session    api    ${BASE_URL}
    ${data}=    Create Dictionary    name=Hector    role=Engineer
    ${resp}=    Post On Session    api    /post    json=${data}
    Log     Status: ${resp.status_code}    level=DEBUG
    Log     TEXT: ${resp.text} 
    Should Be Equal As Integers    ${resp.status_code}    200
    Dictionary Should Contain Value    ${resp.json()["json"]}    Hector

Status Code Check
    [Tags]    negative
    Create Session    api    ${BASE_URL}
    ${resp}=    GET On Session    api    url=${BASEURL}/status/404    expected_status=any
    Log     TEXT: ${resp.text} 
    #log to Console   Status: ${resp.status_code}
    Should Be Equal As Integers    ${resp.status_code}    404

Basic Auth Failure
    [Tags]    auth
    Create Session    api    ${BASE_URL}
    ${resp}=    GET On Session    api    url=${BASEURL}/basic-auth/user/pass    expected_status=any
    Log     TEXT: ${resp.text} 
    Should Be Equal As Integers    ${resp.status_code}    401

Basic Auth Success
    [Tags]    auth
    Create Session    api    ${BASE_URL}
    ${resp}=    GET On Session    api    url=${BASEURL}/basic-auth/user/pass    auth=user:pass
    Log     TEXT: ${resp.text} 
    Should Be Equal As Integers    ${resp.status_code}    200
    Should Be True    ${resp.json()["authenticated"]}

