*** Settings ***
Library    RequestsLibrary

*** Variables ***
${BASE_URL}    %{BASE_URL}

*** Test Cases ***
Test GET Endpoint
    Create Session    api    ${BASE_URL}
    ${resp}=    Get Request    api    /get
    Should Be Equal As Integers    ${resp.status_code}    200

